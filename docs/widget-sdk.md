# Assistant Matrix SDK

This is the first Python SDK scaffold for future store widgets.

Current import surface:

```python
from assistant_matrix_sdk import ConfigField, MatrixCanvas, Widget, WidgetContext
from assistant_matrix_sdk import WidgetPermission, WidgetPreview, WidgetTrigger
```

Minimal widget:

```python
class HelloWidget(Widget):
    id = "example.hello"
    name = "Hello"
    version = "0.1.0"
    summary = "Simple hello-world matrix widget."
    author = "Your Name"
    category = "custom"
    preview_media = WidgetPreview(description="Shows a message on the matrix.")
    triggers = [WidgetTrigger("schedule.rotation", default_enabled=True)]

    config = [
        ConfigField.string("message", label="Message", default="HI"),
    ]

    def render(self, canvas: MatrixCanvas, context: WidgetContext) -> None:
        canvas.background("#000000")
        canvas.text(2, 2, context.config.get("message", "HI"), "#ffffff")
```

Preview a widget frame:

```python
widget = HelloWidget()
widget.preview("preview.png", WidgetContext(config={"message": "HI"}))
```

## Author CLI

The package exposes a small creator CLI:

```bash
poetry run assistant-matrix-widget init user.hello --name "Hello Matrix" --category custom
cd user.hello
poetry run assistant-matrix-widget manifest docs.examples.weather_badge_widget:WeatherBadgeWidget --output widget.toml
poetry run assistant-matrix-widget preview docs.examples.weather_badge_widget:WeatherBadgeWidget --output previews/matrix-64.png --config "{\"label\":\"HOME\",\"temperature\":72,\"condition\":\"sunny\"}"
poetry run assistant-matrix-widget validate widget.toml
poetry run assistant-matrix-widget package . --output-dir dist
poetry run assistant-matrix-widget publish . --store-dir store-dist --base-url https://store.example.com --index store-index.json
```

For shells that make inline JSON awkward, `preview --config @config.json` reads the preview config from a file.

`init` creates the recommended package structure:

```text
widget.toml
README.md
renderer/
  __init__.py
  widget.py
previews/
assets/
```

The generated `widget.toml` is the store contract. It contains:

- widget id, name, version, summary, author, category, runtime, entrypoint, matrix size, and license
- preview media paths
- permissions and reasons
- config fields the Assistant Matrix UI can render
- trigger hints for rotation or event-based display rules

The Store and Plugins pages use `preview.card_gif` / `previewGifUrl` first and fall back to `preview.matrix_png` / `matrixPreviewUrl`. If neither is present, the UI shows a generated placeholder based on the widget category/id.

Trigger events are delivered through the display API:

```bash
curl -X POST http://<pi-host>:3000/api/display/events \
  -H "Content-Type: application/json" \
  -d '{"event":"spotify.playback_started","payload":{"source":"spotify"}}'
```

The app evaluates saved display policy trigger rules and temporarily runs the matching widget.

Packaging writes `dist/<widget-id>-<version>.tar.gz` and prints a SHA256 that can be copied into the store index.

Publishing writes an object-store-ready layout:

```text
store-dist/
  store-index.json
  widgets/
    <widget-id>/
      <version>/
        widget.toml
        <widget-id>-<version>.tar.gz
        previews/
          card.gif
          matrix-64.png
```

The `--base-url` is used to generate public `manifestUrl`, `archiveUrl`, and preview URLs in the index. The resulting folder can be uploaded to GitHub Pages, S3, Cloudflare R2, or any static file host.

Point the Pi at the published index from Assistant Matrix settings:

```text
Widget Store -> Store index URL -> https://store.example.com/store-index.json
```

The same value is persisted as `store.indexUrl` in `data/config.json`.

On the Pi, the lifecycle APIs are:

```text
POST   /api/widgets/install
DELETE /api/widgets/local/<widget-id>
POST   /api/widgets/local/<widget-id>/config
POST   /api/widgets/local/<widget-id>/apply
```

Calling install again for the same widget id updates the local package and store metadata.

The SDK currently provides:

- `MatrixCanvas` backed by Pillow.
- `WidgetContext` for config, state, assets, frame index, and event payload.
- `ConfigField` helpers for manifest-compatible config forms.
- `Widget` base class with `setup`, `render`, `teardown`, and `preview`.
- `WidgetPreview`, `WidgetPermission`, and `WidgetTrigger` helpers for publishing metadata.
- `assistant-matrix-widget` CLI for scaffolding, manifest, preview, validation, packaging, and static-store publishing.
- Local package execution for installed Python widgets that provide `widget.toml` and a Python entrypoint.

Still future work:

- Dependency isolation for third-party widget packages beyond the SDK and app dependencies.

See [docs/examples/weather_badge_widget.py](examples/weather_badge_widget.py) for a complete example.
