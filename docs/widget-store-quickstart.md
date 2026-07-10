# Widget Store Quickstart

This guide walks through the current V1 flow:

1. create a Python widget
2. render a 64x64 preview
3. package it
4. publish a static store folder
5. point the Pi at the store
6. install, configure, and run the widget
7. optionally rotate or trigger it

The V1 store can be any static file host: GitHub Pages, S3, Cloudflare R2, nginx, or a local file path during development.

## 1. Create a Widget

From the repo root:

```bash
poetry run assistant-matrix-widget init user.hello --name "Hello Matrix" --category custom
cd user.hello
```

The generated folder is the package root:

```text
widget.toml
README.md
renderer/
  __init__.py
  widget.py
previews/
assets/
```

The runtime entrypoint in `widget.toml` points to the Python class exported by `renderer/widget.py`:

```toml
[widget]
id = "user.hello"
name = "Hello Matrix"
version = "0.1.0"
runtime = "python"
entrypoint = "renderer.widget:WidgetRenderer"
matrix_size = "64x64"
```

## 2. Edit Config Metadata

Config fields in `widget.toml` become UI controls in Assistant Matrix.

Example:

```toml
[[config]]
key = "message"
label = "Message"
type = "string"
default = "HI"
placeholder = "HI"
```

Supported field types:

- `string`
- `number`
- `boolean`
- `select`
- `secret`
- `location`
- `color`

Select fields must use inline `{label, value}` option objects:

```toml
[[config]]
key = "theme"
label = "Theme"
type = "select"
default = "blue"
options = [{ label = "Blue", value = "blue" }, { label = "Green", value = "green" }]
```

## 3. Render a Matrix Preview

Every publishable widget needs a static 64x64 preview PNG.

```bash
poetry run assistant-matrix-widget preview renderer.widget:UserHelloWidget --output previews/matrix-64.png --config '{"message":"OK"}'
```

If your shell makes inline JSON awkward, put the config in a file:

```json
{
  "message": "OK"
}
```

Then run:

```bash
poetry run assistant-matrix-widget preview renderer.widget:UserHelloWidget --output previews/matrix-64.png --config @preview-config.json
```

An animated store-card GIF is optional:

```text
previews/card.gif
```

If `card.gif` exists and is declared in `widget.toml`, the Store UI uses it first. Otherwise it falls back to `matrix-64.png`.

## 4. Validate and Package

Validate the manifest shape:

```bash
poetry run assistant-matrix-widget validate widget.toml
```

Package the widget archive:

```bash
poetry run assistant-matrix-widget package . --output-dir dist
```

Package validation checks:

- valid widget id
- semantic-ish version such as `0.1.0`
- supported category and runtime
- renderable config fields
- permissions with reasons
- trigger event names
- declared Python entrypoint file exists
- required `preview.matrix_png` exists

Machine-readable schemas are available for external tooling:

- [Widget manifest schema](schemas/widget-manifest.schema.json)
- [Widget store index schema](schemas/widget-store-index.schema.json)

The package command writes:

```text
dist/user.hello-0.1.0.tar.gz
```

and prints the SHA256 digest.

## 5. Publish a Static Store

Publish to a local object-store-shaped folder:

```bash
poetry run assistant-matrix-widget publish . --store-dir ../store-dist --base-url https://store.example.com
```

Output:

```text
store-dist/
  store-index.json
  widgets/
    user.hello/
      0.1.0/
        widget.toml
        user.hello-0.1.0.tar.gz
        previews/
          matrix-64.png
          card.gif
```

`store-index.json` contains the fields the Pi needs:

```json
{
  "schemaVersion": 1,
  "widgets": [
    {
      "id": "user.hello",
      "name": "Hello Matrix",
      "version": "0.1.0",
      "summary": "Hello Matrix widget for Assistant Matrix.",
      "category": "custom",
      "author": "Assistant Matrix",
      "manifestUrl": "https://store.example.com/widgets/user.hello/0.1.0/widget.toml",
      "archiveUrl": "https://store.example.com/widgets/user.hello/0.1.0/user.hello-0.1.0.tar.gz",
      "previewGifUrl": "",
      "matrixPreviewUrl": "https://store.example.com/widgets/user.hello/0.1.0/previews/matrix-64.png",
      "sha256": "..."
    }
  ]
}
```

Upload the full `store-dist/` folder contents to your static host.

## 6. Point the Pi at the Store

In the Assistant Matrix UI:

```text
Settings -> Widget Store -> Store index URL
```

Use:

```text
https://store.example.com/store-index.json
```

Or save it through the config API:

```bash
curl -X POST http://<pi-host>:3000/api/config \
  -H "Content-Type: application/json" \
  -d @config.json
```

The saved value lands in:

```json
{
  "store": {
    "indexUrl": "https://store.example.com/store-index.json"
  }
}
```

For local development, `indexUrl` can be a filesystem path.

## 7. Install, Configure, and Run

Browse the store:

```bash
curl http://<pi-host>:3000/api/widgets/store
```

Install the widget:

```bash
curl -X POST http://<pi-host>:3000/api/widgets/install \
  -H "Content-Type: application/json" \
  -d '{"widgetId":"user.hello"}'
```

The Pi downloads the archive, validates SHA256 when present, rejects unsafe archive paths and links, checks that `widget.toml` matches the store entry, and extracts to:

```text
data/widgets/packages/user.hello/
```

Save config:

```bash
curl -X POST http://<pi-host>:3000/api/widgets/local/user.hello/config \
  -H "Content-Type: application/json" \
  -d '{"config":{"message":"OK"}}'
```

Apply it immediately:

```bash
curl -X POST http://<pi-host>:3000/api/widgets/local/user.hello/apply \
  -H "Content-Type: application/json" \
  -d '{"config":{"message":"OK"}}'
```

The runtime restarts in widget mode and runs:

```text
spotify_matrix.py --display-mode widget --widget-dir data/widgets/packages/user.hello --widget-config data/widgets/config/user.hello.json
```

## 8. Rotate Widgets

Save a display policy:

```bash
curl -X POST http://<pi-host>:3000/api/display/policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy": {
      "mode": "rotation",
      "activeWidgetId": "core.clock",
      "rotation": [
        {"widgetId": "core.weather", "durationSeconds": 60, "enabled": true},
        {"widgetId": "user.hello", "durationSeconds": 30, "enabled": true}
      ],
      "triggers": []
    }
  }'
```

Start rotation:

```bash
curl -X POST http://<pi-host>:3000/api/display/policy/apply
```

Stop rotation:

```bash
curl -X POST http://<pi-host>:3000/api/display/policy/stop
```

## 9. Trigger Widgets From Events

Save a trigger rule:

```bash
curl -X POST http://<pi-host>:3000/api/display/policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy": {
      "mode": "single",
      "activeWidgetId": "core.clock",
      "rotation": [],
      "triggers": [
        {
          "event": "spotify.playback_started",
          "widgetId": "core.spotify",
          "enabled": true,
          "priority": 50,
          "minDurationSeconds": 15
        }
      ]
    }
  }'
```

Submit an event:

```bash
curl -X POST http://<pi-host>:3000/api/display/events \
  -H "Content-Type: application/json" \
  -d '{"event":"spotify.playback_started","payload":{"source":"spotify"}}'
```

Or use the command API:

```bash
curl -X POST http://<pi-host>:3000/api/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"trigger_event","value":"spotify.playback_started"}'
```

## Publishing Checklist

Before publishing a widget publicly, confirm:

- `widget.id` is stable and namespaced, for example `munkeops.weather`.
- `widget.version` changes whenever the archive changes.
- `summary` is short enough for a store card.
- `preview.matrix_png` exists and is representative.
- `preview.card_gif` exists when you want an animated store-card preview.
- Config fields have stable keys because saved user config depends on them.
- Secrets use `type = "secret"`.
- Permissions explain why network, location, account, or device access is needed.
- Trigger hints use stable event names such as `spotify.playback_started`.
- `sha256` in the store index matches the archive.
