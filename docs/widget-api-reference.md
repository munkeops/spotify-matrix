# Assistant Matrix API Reference

This document describes the implemented local APIs used by the Assistant Matrix UI, widget store, future voice agents, and automation clients.

Base URL on the Pi:

```text
http://<pi-host>:3000
```

All JSON requests should use:

```text
Content-Type: application/json
```

## Store APIs

### List Store Widgets

```text
GET /api/widgets/store
```

Returns widgets from the configured store index. The index source comes from `store.indexUrl` in `data/config.json`, unless `ASSISTANT_MATRIX_WIDGET_STORE_INDEX` is set.

Response:

```json
{
  "schemaVersion": 1,
  "widgets": [
    {
      "id": "example.weather",
      "name": "Weather",
      "version": "1.0.0",
      "summary": "Weather, AQI, UV, and wind.",
      "category": "information",
      "author": "Assistant Matrix",
      "manifestUrl": "https://store.example.com/widgets/example.weather/1.0.0/widget.toml",
      "archiveUrl": "https://store.example.com/widgets/example.weather/1.0.0/example.weather-1.0.0.tar.gz",
      "previewGifUrl": "https://store.example.com/widgets/example.weather/1.0.0/previews/card.gif",
      "matrixPreviewUrl": "https://store.example.com/widgets/example.weather/1.0.0/previews/matrix-64.png",
      "sha256": "...",
      "installed": false
    }
  ]
}
```

### Get Store Widget

```text
GET /api/widgets/store/{widget_id}
```

Returns one store catalog entry.

### Install Or Update Widget

```text
POST /api/widgets/install
```

Request:

```json
{
  "widgetId": "example.weather"
}
```

Behavior:

- Adds or updates the installed widget metadata.
- Downloads or reads the archive when `archiveUrl` is reachable.
- Validates `sha256` when present.
- Extracts the package to `data/widgets/packages/<widget-id>/`.
- Calling this again updates/reinstalls the same widget id.

Response:

```json
{
  "ok": true,
  "widget": {
    "manifest": {
      "id": "example.weather",
      "name": "Weather",
      "runtime": "python",
      "entrypoint": "renderer.widget:WeatherWidget"
    },
    "installed": true,
    "builtIn": false,
    "enabled": true,
    "configurable": true,
    "active": false
  }
}
```

## Local Widget APIs

Local widgets include built-in `core.*` widgets and downloaded store widgets.

### List Local Widgets

```text
GET /api/widgets/local
```

Returns installed widgets with manifests, config schemas, permissions, triggers, and active state.

### Get Local Widget

```text
GET /api/widgets/local/{widget_id}
```

Returns a single local widget.

### Uninstall Local Widget

```text
DELETE /api/widgets/local/{widget_id}
```

Only downloaded store widgets are uninstallable. Built-in `core.*` widgets are part of the app.

Behavior:

- Stops the display policy runner.
- Stops the current runtime.
- Removes installed metadata.
- Deletes package files from `data/widgets/packages/<widget-id>/`.
- Deletes saved widget config from `data/widgets/config/<widget-id>.json`.
- Removes rotation and trigger policy references.
- Falls back to Spotify if the removed widget was active.

Response:

```json
{
  "ok": true,
  "widgetId": "example.weather"
}
```

### Get Widget Config

```text
GET /api/widgets/local/{widget_id}/config
```

Returns the saved config for the widget. If no config exists for an external widget, defaults from `widget.toml` are returned.

Response:

```json
{
  "widgetId": "example.weather",
  "config": {
    "postalCode": "60601",
    "temperatureUnit": "fahrenheit"
  }
}
```

### Save Widget Config

```text
POST /api/widgets/local/{widget_id}/config
```

Request:

```json
{
  "config": {
    "postalCode": "60601",
    "temperatureUnit": "fahrenheit"
  }
}
```

Built-in widget config is saved into `data/config.json`. External widget config is saved under `data/widgets/config/<widget-id>.json`.

### Apply Widget

```text
POST /api/widgets/local/{widget_id}/apply
```

Request:

```json
{
  "config": {
    "postalCode": "60601"
  }
}
```

Behavior:

- Saves optional config override.
- Stops any display policy scheduler.
- Switches active display mode to the widget.
- Restarts the runtime automatically.

## Display Policy APIs

Display policies decide whether the matrix runs one widget continuously or rotates through widgets.

### Get Display Policy

```text
GET /api/display/policy
```

Response:

```json
{
  "policy": {
    "mode": "rotation",
    "activeWidgetId": "core.spotify",
    "rotation": [
      {
        "widgetId": "core.weather",
        "durationSeconds": 60,
        "enabled": true
      }
    ],
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
}
```

### Save Display Policy

```text
POST /api/display/policy
```

Request:

```json
{
  "policy": {
    "mode": "single",
    "activeWidgetId": "core.clock",
    "rotation": [],
    "triggers": []
  }
}
```

The backend validates referenced widget ids.

The Plugins page Display Policy panel edits `mode`, `activeWidgetId`, `rotation`, and `triggers`. Trigger rows map directly to `policy.triggers`.

### Apply Display Policy

```text
POST /api/display/policy/apply
```

Behavior:

- `single`: applies `activeWidgetId` and stops scheduling.
- `rotation`: starts a background scheduler using enabled rotation items.

### Stop Display Policy Runner

```text
POST /api/display/policy/stop
```

Stops the rotation scheduler.

### Get Display Policy State

```text
GET /api/display/policy/state
```

Response:

```json
{
  "schedulerRunning": true,
  "activeWidgetId": "core.weather",
  "mode": "rotation",
  "activeEvent": null,
  "lastError": null
}
```

## Event APIs

Events temporarily override the current display based on saved trigger rules.

### Submit Display Event

```text
POST /api/display/events
```

Request:

```json
{
  "event": "spotify.playback_started",
  "payload": {
    "source": "spotify"
  }
}
```

Behavior:

- Finds enabled `policy.triggers` matching `event`.
- Chooses the highest-priority rule.
- Applies the rule's widget.
- Reports `activeEvent`.
- Resumes the saved display policy after `minDurationSeconds`.

Response:

```json
{
  "ok": true,
  "matched": true,
  "event": "spotify.playback_started",
  "widgetId": "core.spotify",
  "state": {
    "schedulerRunning": false,
    "activeWidgetId": "core.spotify",
    "mode": "rotation",
    "activeEvent": "spotify.playback_started",
    "lastError": null
  },
  "runtime": {}
}
```

## Config APIs

### Get Config

```text
GET /api/config
```

Returns public app config. Spotify Client Secret is masked.

Relevant store config:

```json
{
  "store": {
    "indexUrl": "https://store.example.com/store-index.json"
  }
}
```

### Save Config

```text
POST /api/config
```

Saves full app config. If `spotify.clientSecret` is `"********"`, the existing secret is preserved.

## Runtime APIs

### Start Runtime

```text
POST /api/runtime/start
```

### Stop Runtime

```text
POST /api/runtime/stop
```

### Apply Runtime

```text
POST /api/runtime/apply
```

Restarts the runtime using saved config.

## Command API

The command API is the stable path for future voice agents and automations.

```text
POST /api/commands
```

Current commands:

- `set_mode`
- `set_widget`
- `set_clock_face`
- `set_brightness`
- `trigger_event`
- `start_runtime`
- `stop_runtime`

Example:

```json
{
  "command": "set_brightness",
  "value": 35
}
```

Run any local widget continuously:

```json
{
  "command": "set_widget",
  "value": "core.weather"
}
```

Submit an event through the saved display policy trigger rules:

```json
{
  "command": "trigger_event",
  "value": "spotify.playback_started"
}
```

`trigger_event` reports whether a policy rule matched and which widget was applied:

```json
{
  "ok": true,
  "matched": true,
  "widgetId": "core.spotify"
}
```

For richer widget behavior, prefer the widget and display policy APIs above.

## Widget Author CLI

The SDK command line tool supports the full local author workflow:

```bash
assistant-matrix-widget init user.hello --name "Hello Matrix"
assistant-matrix-widget validate widget.toml
assistant-matrix-widget preview renderer.widget:UserHelloWidget --output previews/matrix-64.png
assistant-matrix-widget package . --output-dir dist
assistant-matrix-widget publish . --store-dir store-dist --base-url https://store.example.com
```

`init` creates:

```text
widget.toml
README.md
renderer/widget.py
renderer/__init__.py
previews/
assets/
```

That folder is the unit that gets packaged, published to the store, installed on the Pi, configured, and run.
