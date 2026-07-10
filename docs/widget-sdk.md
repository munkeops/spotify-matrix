# Assistant Matrix SDK

This is the first Python SDK scaffold for future store widgets.

Current import surface:

```python
from assistant_matrix_sdk import ConfigField, MatrixCanvas, Widget, WidgetContext
```

Minimal widget:

```python
class HelloWidget(Widget):
    id = "example.hello"
    name = "Hello"

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

The SDK currently provides:

- `MatrixCanvas` backed by Pillow.
- `WidgetContext` for config, state, assets, frame index, and event payload.
- `ConfigField` helpers for manifest-compatible config forms.
- `Widget` base class with `setup`, `render`, `teardown`, and `preview`.

Still future work:

- Runtime package loading from installed store archives.
- Manifest validation CLI.
- Widget packaging CLI.
- Store publishing CLI.
- Event-driven widget execution.

See [docs/examples/weather_badge_widget.py](examples/weather_badge_widget.py) for a complete example.
