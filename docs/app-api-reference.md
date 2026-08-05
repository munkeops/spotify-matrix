# Assistant Matrix API Reference

This document describes the implemented local APIs used by the Assistant Matrix UI, app store, future voice agents, and automation clients.

Base URL on the Pi:

```text
http://<pi-host>:3000
```

All JSON requests should use:

```text
Content-Type: application/json
```

## Store APIs

### List Store Apps

```text
GET /api/apps/store
```

Returns apps from the configured store index. The index source comes from `store.indexUrl` in `data/config.json`, unless `ASSISTANT_MATRIX_APP_STORE_INDEX` is set.

Response:

```json
{
  "schemaVersion": 1,
  "apps": [
    {
      "id": "example.weather",
      "name": "Weather",
      "version": "1.0.0",
      "summary": "Weather, AQI, UV, and wind.",
      "category": "information",
      "author": "Assistant Matrix",
      "manifestUrl": "https://store.example.com/apps/example.weather/1.0.0/app.toml",
      "archiveUrl": "https://store.example.com/apps/example.weather/1.0.0/example.weather-1.0.0.tar.gz",
      "previewGifUrl": "https://store.example.com/apps/example.weather/1.0.0/previews/card.gif",
      "matrixPreviewUrl": "https://store.example.com/apps/example.weather/1.0.0/previews/matrix-64.png",
      "sha256": "...",
      "installed": false
    }
  ]
}
```

### Get Store App

```text
GET /api/apps/store/{app_id}
```

Returns one store catalog entry.

### Install Or Update App

```text
POST /api/apps/install
```

Request:

```json
{
  "appId": "example.weather"
}
```

Behavior:

- Adds or updates the installed app metadata.
- Downloads or reads the archive when `archiveUrl` is reachable.
- Validates `sha256` when present.
- Extracts the package to `data/apps/packages/<app-id>/`.
- Calling this again updates/reinstalls the same app id.

Response:

```json
{
  "ok": true,
  "app": {
    "manifest": {
      "id": "example.weather",
      "name": "Weather",
      "runtime": "python",
      "entrypoint": "renderer.app:WeatherApp"
    },
    "installed": true,
    "builtIn": false,
    "enabled": true,
    "configurable": true,
    "active": false
  }
}
```

## Local App APIs

Local apps include built-in `core.*` apps and downloaded store apps.

### List Local Apps

```text
GET /api/apps/local
```

Returns installed apps with manifests, config schemas, permissions, triggers, and active state.

### Get Local App

```text
GET /api/apps/local/{app_id}
```

Returns a single local app.

### Uninstall Local App

```text
DELETE /api/apps/local/{app_id}
```

Only downloaded store apps are uninstallable. Built-in `core.*` apps are part of the app.

Behavior:

- Stops the display policy runner.
- Stops the current runtime.
- Removes installed metadata.
- Deletes package files from `data/apps/packages/<app-id>/`.
- Deletes saved app config from `data/apps/config/<app-id>.json`.
- Removes rotation and trigger policy references.
- Falls back to Spotify if the removed app was active.

Response:

```json
{
  "ok": true,
  "appId": "example.weather"
}
```

### Get App Config

```text
GET /api/apps/local/{app_id}/config
```

Returns the saved config for the app. If no config exists for an external app, defaults from `app.toml` are returned.

Response:

```json
{
  "appId": "example.weather",
  "config": {
    "postalCode": "60601",
    "temperatureUnit": "fahrenheit"
  }
}
```

### Save App Config

```text
POST /api/apps/local/{app_id}/config
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

Built-in app config is saved into `data/config.json`. External app config is saved under `data/apps/config/<app-id>.json`.

### Apply App

```text
POST /api/apps/local/{app_id}/apply
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
- Switches active display mode to the app.
- Restarts the runtime automatically.

## Display Policy APIs

Display policies decide whether the matrix runs one app continuously or rotates through apps.

### Get Display Policy

```text
GET /api/display/policy
```

Response:

```json
{
  "policy": {
    "mode": "rotation",
    "activeAppId": "core.spotify",
    "rotation": [
      {
        "appId": "core.weather",
        "durationSeconds": 60,
        "enabled": true
      }
    ],
    "triggers": [
      {
        "event": "spotify.playback_started",
        "appId": "core.spotify",
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
    "activeAppId": "core.clock",
    "rotation": [],
    "triggers": []
  }
}
```

The backend validates referenced app ids.

The Apps page Display Policy panel edits `mode`, `activeAppId`, `rotation`, and `triggers`. Trigger rows map directly to `policy.triggers`.

### Apply Display Policy

```text
POST /api/display/policy/apply
```

Behavior:

- `single`: applies `activeAppId` and stops scheduling.
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
  "activeAppId": "core.weather",
  "mode": "rotation",
  "activeEvent": null,
  "lastError": null
}
```

## Event APIs

Events temporarily override the current display based on saved trigger rules.

Built-in Spotify runtime events:

- `spotify.playback_started`
- `spotify.playback_paused`
- `spotify.playback_stopped`

When the FastAPI supervisor starts `spotify_matrix.py`, it passes the local event endpoint through `--event-api-url`. Standalone CLI runs can omit that flag to disable event posting.

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
- Applies the rule's app.
- Reports `activeEvent`.
- Resumes the saved display policy after `minDurationSeconds`.

Response:

```json
{
  "ok": true,
  "matched": true,
  "event": "spotify.playback_started",
  "appId": "core.spotify",
  "state": {
    "schedulerRunning": false,
    "activeAppId": "core.spotify",
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

## Game APIs

Every built-in game shares these routes. The Tetris specific routes below are
kept for compatibility and add its structured board state.

### List Games

```text
GET /api/games
```

```json
{
  "activeGameId": "pacman",
  "running": true,
  "games": [
    {
      "id": "pacman",
      "name": "Pac-Man",
      "summary": "Clear the maze while four ghosts hunt you down.",
      "appId": "core.pacman",
      "layout": "dpad",
      "actions": ["up", "down", "left", "right", "pause", "resume", "togglePause", "restart"],
      "active": true
    }
  ]
}
```

`layout` tells a controller which pad to render: `dpad`, `horizontal`,
`vertical`, `tap`, or `tetris`. `actions` is the full set the game accepts.

Games are apps, so this list is whatever is installed. Drop a package into
`<data>/apps/packages/` and it appears here. See
[game apps](game-apps.md).

Put a game on the panel with the normal app route:

```text
POST /api/apps/local/core.pacman/apply
```

### Send Controller Input

```text
POST /api/games/{game_id}/input
```

```json
{ "action": "left" }
```

Actions across the set: `up`, `down`, `left`, `right`, `fire`, `flap`, `drop`,
`softDrop`, `hardDrop`, `rotateCw`, `rotateCcw`, `hold`, `p2Up`, `p2Down`,
`pause`, `resume`, `togglePause`, `restart`. A game ignores actions it does not
declare.

Each command is stamped with an increasing sequence number. The runtime applies
everything newer than the last sequence it saw on its next frame, so repeated
presses are never dropped or replayed twice.

### Read The Live Frame

```text
GET /api/games/{game_id}/state
```

```json
{
  "gameId": "pacman",
  "live": true,
  "running": true,
  "active": true,
  "state": {
    "game": "pacman",
    "status": "playing",
    "hud": { "Score": 1240, "Lives": 3, "Level": 2 },
    "palette": ["#000000", "#283ebe", "#e8d2aa", "#fadc3c"],
    "pixels": ["0000000000…", "0111111110…"],
    "updatedAt": 1754308800.0
  }
}
```

`pixels` is one string per panel row; each character indexes `palette`, encoded
base62. That is the whole frame, so one client can mirror any game. `status` is
`playing`, `paused`, `gameOver` or `won`. `live` is false when nothing has
published a frame recently, which means no game is running.

Once a game finishes, a fire or drop button starts a new one, but only after a
short grace period so the final score is readable.

## Tetris APIs

`/api/tetris/input` and `/api/tetris/state` behave as before and additionally
return the structured board (`board`, `active`, `ghost`, `next`, `hold`).

```text
POST /api/tetris/input
GET  /api/tetris/state
```

## Command API

The command API is the stable path for future voice agents and automations.

```text
POST /api/commands
```

Current commands:

- `set_mode`
- `set_app`
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

Run any local app continuously:

```json
{
  "command": "set_app",
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

`trigger_event` reports whether a policy rule matched and which app was applied:

```json
{
  "ok": true,
  "matched": true,
  "appId": "core.spotify"
}
```

For richer app behavior, prefer the app and display policy APIs above.

## App Author CLI

The SDK command line tool supports the full local author workflow:

```bash
assistant-matrix-app init user.hello --name "Hello Matrix"
assistant-matrix-app validate app.toml
assistant-matrix-app preview renderer.app:UserHelloApp --output previews/matrix-64.png
assistant-matrix-app package . --output-dir dist
assistant-matrix-app publish . --store-dir store-dist --base-url https://store.example.com
assistant-matrix-app validate-store store-dist/store-index.json
```

`init` creates:

```text
app.toml
README.md
renderer/app.py
renderer/__init__.py
previews/
assets/
```

Before packaging or publishing, the app folder must contain:

- `app.toml` with valid id, name, semantic version, summary, runtime, entrypoint, category, and matrix size metadata.
- The declared Python entrypoint file, for example `renderer/app.py`.
- The required matrix preview declared by `preview.matrix_png`, usually `previews/matrix-64.png`.
- Optional `preview.card_gif`; when present it becomes the animated store-card preview, and when absent the store index leaves `previewGifUrl` empty.
- Config fields with stable `key`, `label`, and supported `type`; select fields need `{label, value}` options.
- Permissions with both `name` and `reason`.
- Trigger hints with an `event` name.

That folder is the unit that gets packaged, published to the store, installed on the Pi, configured, and run.

Machine-readable contracts:

- [App manifest schema](schemas/app-manifest.schema.json)
- [App store index schema](schemas/app-store-index.schema.json)
