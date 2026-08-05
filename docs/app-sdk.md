# Assistant Matrix SDK

This is the first Python SDK scaffold for future store apps.

Current import surface:

```python
from assistant_matrix_sdk import ConfigField, MatrixCanvas, App, AppContext
from assistant_matrix_sdk import AppPermission, AppPreview, AppTrigger
```

Minimal app:

```python
class HelloApp(App):
    id = "example.hello"
    name = "Hello"
    version = "0.1.0"
    summary = "Simple hello-world matrix app."
    author = "Your Name"
    category = "custom"
    preview_media = AppPreview(description="Shows a message on the matrix.")
    triggers = [AppTrigger("schedule.rotation", default_enabled=True)]

    config = [
        ConfigField.string("message", label="Message", default="HI"),
    ]

    def render(self, canvas: MatrixCanvas, context: AppContext) -> None:
        canvas.background("#000000")
        canvas.text(2, 2, context.config.get("message", "HI"), "#ffffff")
```

Preview a app frame:

```python
app = HelloApp()
app.preview("preview.png", AppContext(config={"message": "HI"}))
```

## Author CLI

The package exposes a small creator CLI:

```bash
poetry run assistant-matrix-app init user.hello --name "Hello Matrix" --category custom
cd user.hello
poetry run assistant-matrix-app manifest docs.examples.weather_badge_app:WeatherBadgeApp --output app.toml
poetry run assistant-matrix-app preview docs.examples.weather_badge_app:WeatherBadgeApp --output previews/matrix-64.png --config "{\"label\":\"HOME\",\"temperature\":72,\"condition\":\"sunny\"}"
poetry run assistant-matrix-app validate app.toml
poetry run assistant-matrix-app package . --output-dir dist
poetry run assistant-matrix-app publish . --store-dir store-dist --base-url https://store.example.com --index store-index.json
poetry run assistant-matrix-app validate-store store-dist/store-index.json
```

For shells that make inline JSON awkward, `preview --config @config.json` reads the preview config from a file.

`init` creates the recommended package structure:

```text
app.toml
README.md
renderer/
  __init__.py
  app.py
previews/
assets/
```

The generated `app.toml` is the store contract. It contains:

- app id, name, version, summary, author, category, runtime, entrypoint, matrix size, and license
- preview media paths
- permissions and reasons
- config fields the Assistant Matrix UI can render
- trigger hints for rotation or event-based display rules

Machine-readable contracts:

- [App manifest schema](schemas/app-manifest.schema.json)
- [App store index schema](schemas/app-store-index.schema.json)

The Store and Apps pages use `preview.card_gif` / `previewGifUrl` first and fall back to `preview.matrix_png` / `matrixPreviewUrl`. `preview.matrix_png` is the required baseline preview for packaging and publishing. `preview.card_gif` is optional; if the file is not present, the published store index leaves `previewGifUrl` empty and the UI uses the matrix PNG. If neither preview URL is available, the UI shows a generated placeholder based on the app category/id.

Trigger events are delivered through the display API:

```bash
curl -X POST http://<pi-host>:3000/api/display/events \
  -H "Content-Type: application/json" \
  -d '{"event":"spotify.playback_started","payload":{"source":"spotify"}}'
```

The app evaluates saved display policy trigger rules and temporarily runs the matching app.

Packaging validates the manifest, Python entrypoint file, and required `preview.matrix_png`, then writes `dist/<app-id>-<version>.tar.gz` and prints a SHA256 that can be copied into the store index.

Publishing writes an object-store-ready layout:

```text
store-dist/
  store-index.json
  apps/
    <app-id>/
      <version>/
        app.toml
        <app-id>-<version>.tar.gz
        previews/
          card.gif
          matrix-64.png
```

The `--base-url` is used to generate public `manifestUrl`, `archiveUrl`, and preview URLs in the index. The resulting folder can be uploaded to GitHub Pages, S3, Cloudflare R2, or any static file host.

Point the Pi at the published index from Assistant Matrix settings:

```text
App Store -> Store index URL -> https://store.example.com/store-index.json
```

The same value is persisted as `store.indexUrl` in `data/config.json`.

On the Pi, the lifecycle APIs are:

```text
POST   /api/apps/install
DELETE /api/apps/local/<app-id>
POST   /api/apps/local/<app-id>/config
POST   /api/apps/local/<app-id>/apply
```

Calling install again for the same app id updates the local package and store metadata.

The SDK currently provides:

- `MatrixCanvas` backed by Pillow.
- `AppContext` for config, state, assets, frame index, and event payload.
- `ConfigField` helpers for manifest-compatible config forms.
- `App` base class with `setup`, `render`, `teardown`, and `preview`.
- `AppPreview`, `AppPermission`, and `AppTrigger` helpers for publishing metadata.
- `assistant-matrix-app` CLI for scaffolding, manifest, preview, validation, packaging, and static-store publishing.
- `validate-store` for checking a static `store-index.json` before upload.
- Local package execution for installed Python apps that provide `app.toml` and a Python entrypoint.

Still future work:

- Dependency isolation for third-party app packages beyond the SDK and app dependencies.

See [docs/examples/weather_badge_app.py](examples/weather_badge_app.py) for a complete example.
