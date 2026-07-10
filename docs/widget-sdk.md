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
poetry run assistant-matrix-widget manifest docs.examples.weather_badge_widget:WeatherBadgeWidget --output widget.toml
poetry run assistant-matrix-widget preview docs.examples.weather_badge_widget:WeatherBadgeWidget --output previews/matrix-64.png --config "{\"label\":\"HOME\",\"temperature\":72,\"condition\":\"sunny\"}"
poetry run assistant-matrix-widget validate widget.toml
poetry run assistant-matrix-widget package . --output-dir dist
```

For shells that make inline JSON awkward, `preview --config @config.json` reads the preview config from a file.

The generated `widget.toml` is the store contract. It contains:

- widget id, name, version, summary, author, category, runtime, entrypoint, matrix size, and license
- preview media paths
- permissions and reasons
- config fields the Assistant Matrix UI can render
- trigger hints for rotation or event-based display rules

Packaging writes `dist/<widget-id>-<version>.tar.gz` and prints a SHA256 that can be copied into the store index.

The SDK currently provides:

- `MatrixCanvas` backed by Pillow.
- `WidgetContext` for config, state, assets, frame index, and event payload.
- `ConfigField` helpers for manifest-compatible config forms.
- `Widget` base class with `setup`, `render`, `teardown`, and `preview`.
- `WidgetPreview`, `WidgetPermission`, and `WidgetTrigger` helpers for publishing metadata.
- `assistant-matrix-widget` CLI for manifest, preview, validation, and packaging.
- Local package execution for installed Python widgets that provide `widget.toml` and a Python entrypoint.

Still future work:

- Store publishing CLI.
- Event-driven widget execution.
- Dependency isolation for third-party widget packages beyond the SDK and app dependencies.

See [docs/examples/weather_badge_widget.py](examples/weather_badge_widget.py) for a complete example.
