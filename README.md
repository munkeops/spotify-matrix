# Spotify Matrix

Shows the current Spotify album art on a 64x64 RGB matrix as a circular record. The album art is cropped to a disk, spun while Spotify reports playback as active, and left stopped at the current angle when paused.

The project now uses a Python-only stack:

- FastAPI setup service in `src/`
- Static HTML/CSS/JS UI in `public/`
- Python OAuth helper in `scripts/oauth_helper.py`
- Runtime display script in `spotify_matrix.py`
- TOML service config in `configs/base_config.toml`

Widget platform docs:

- [Widget store roadmap](docs/widget-store-roadmap.md)
- [Widget store quickstart](docs/widget-store-quickstart.md)
- [Widget SDK](docs/widget-sdk.md)
- [Widget API reference](docs/widget-api-reference.md)
- [Widget manifest schema](docs/schemas/widget-manifest.schema.json)
- [Widget store index schema](docs/schemas/widget-store-index.schema.json)
- [Game plugins](docs/game-plugins.md)
- [Game audio](docs/game-audio.md)
- [Mini-joystick module](docs/mini-joystick.md)
- [Bluetooth game controller](docs/game-controller.md)

## Layout

This repo follows the service structure used by the synthesis Python repos:

```text
configs/
  base_config.toml
src/
  main.py
  server.py
  api/http/rest/
  domain/models/
  domain/services/
  utils/
public/
scripts/
```

Runtime secrets are stored under `data/`, which is ignored by Git:

- `data/config.json` - Spotify credentials and matrix settings.
- `data/spotify_token.json` - Spotify access and refresh token.

The Dockerfile keeps the base Python dependency install and the `rpi-rgb-led-matrix` native binding install in separate layers. If the matrix binding fails to compile, rebuilds can reuse the Poetry dependency layer while debugging the native build step.

## Hardware feasibility

Docker deployment is possible on Raspberry Pi, but HUB75 matrix output needs direct GPIO access. The Compose service uses `privileged: true` and host networking for that reason.

Pi 3/4/5-class hardware should be viable. Pi Zero and other low-memory boards can be fragile because the RGB matrix bindings compile native code and the runtime rotates album art continuously. Panel compatibility still depends on the panel, HAT wiring, `hardwareMapping`, `gpioSlowdown`, scan pattern, and refresh settings.

## Spotify auth without router port forwarding

Spotify requires HTTPS redirect URIs except explicit loopback IPs such as `http://127.0.0.1:PORT/callback`; `localhost` is not accepted for newly validated apps. This repo avoids router port forwarding by doing OAuth on your laptop:

1. Add this loopback redirect URI in the Spotify developer dashboard:

   ```text
   http://127.0.0.1:8888/callback
   ```

2. Open the Pi setup UI from your laptop:

   ```text
   http://raspberrypi.local:3000
   ```

3. Save the Spotify Client ID and Client Secret.
4. Click **Create Pairing Token**.
5. Run the displayed Python helper command on your laptop:

   ```bash
   python scripts/oauth_helper.py --pi http://raspberrypi.local:3000 --pairing-token <token>
   ```

The helper opens Spotify in your laptop browser, receives the callback on `127.0.0.1`, exchanges the code for tokens, and posts the refresh token back to the Pi over your LAN.

## Docker deployment on Pi

Install Docker and Docker Compose on the Pi, then run:

```bash
docker compose up --build
```

The FastAPI setup UI listens on port `3000`.

The container installs `rpi-rgb-led-matrix` from the upstream GitHub repository during build, so the Pi needs network access for the first build.

## Cloudflare Tunnel

The Compose file includes a `cloudflared` sidecar. In Cloudflare Zero Trust, create a tunnel and configure the public hostname to forward to:

```text
http://localhost:3000
```

On the Pi, save the tunnel token in a local `.env` file:

```bash
CLOUDFLARED_TOKEN=your_cloudflare_tunnel_token
```

Then start both containers:

```bash
docker compose --profile tunnel up -d --build
```

For full container-managed Spotify OAuth, add this HTTPS callback to the Spotify developer dashboard, replacing the hostname with your Cloudflare hostname:

```text
https://spotify-matrix.example.com/api/auth/callback
```

Save the same HTTPS callback in the setup UI's Redirect URI field, then click **Open Spotify Login**. Spotify will redirect back through Cloudflare to `/api/auth/callback`, and the refresh token will be saved under `data/spotify_token.json`.

The laptop helper flow remains available for local setup without a domain.

## Portainer

The Compose file also includes Portainer CE behind an optional `admin` profile. Start it with:

```bash
docker compose --profile admin up -d portainer
```

Then open:

```text
http://raspberrypi.local:9000
```

or:

```text
https://raspberrypi.local:9443
```

Portainer state is stored in the named Docker volume `portainer_data`. The service mounts `/var/run/docker.sock` so it can manage containers on the Pi.

## Local development

Install dependencies with Poetry:

```bash
poetry install
```

Or with pip:

```bash
python -m pip install -r requirements.txt
```

Start the FastAPI setup service:

```bash
poetry run python -m src.main
```

On Raspberry Pi OS releases that only ship Python 3.13, use the same Poetry environment:

```bash
poetry env use python3
poetry install --only main
```

Run the Python renderer without matrix hardware:

```bash
python spotify_matrix.py --mock-output data/frame.png --once
```

Render local preview frames:

```bash
python spotify_matrix.py --preview-frames data/preview
```

## The arcade

Nine games run on the panel and are played from the app, a phone, or the
mini-joystick module. They live on the **Play** shelf of the Store and of your
installed plugins; tap one to put it on the matrix and its gamepad opens with a
live mirror of the panel.

Both the Store and the Plugins page are split into the same three shelves —
**Apps**, **Play** and **Creative** — so a game is in the same place whether you
are browsing for one or managing what you already have.

| Game | Controls | Notes |
|---|---|---|
| Tetris | move, rotate, hold, hard drop | next/hold/score panel, ghost piece |
| Pac-Man | d-pad | full 28x29 maze, four ghosts with scatter/chase/frightened targeting |
| Snake | d-pad | speeds up as you eat; walls can be turned off to wrap |
| Breakout | left/right, fire | five brick rows, three lives, faster each level |
| Space Invaders | left/right, fire | descending waves, bombs, three lives |
| Flappy | one button | tap to fly, tracks your best |
| Pong | up/down | versus the computer, or a second phone on the P2 buttons |
| Connect Four | left/right, drop | hot seat or versus the computer |
| Battleship | d-pad, fire | two 10x10 grids; the computer hunts around its hits |

Every game shares one contract: the runtime steps it, renders a 64x64 frame, and
publishes that frame as a palette plus one row string per line. The app decodes
it onto a canvas, so the mirror shows exactly what the panel shows and adding a
game needs no new UI. Games live in `matrix_games/`; adding one is a module plus
a single entry in `matrix_games/__init__.py`.

Controller input reaches the runtime through a sequenced command queue under
`data/widgets/state/`, so presses are never dropped or replayed twice:

```bash
curl http://<pi-host>:3000/api/games
curl -X POST http://<pi-host>:3000/api/games/pacman/input -H "Content-Type: application/json" -d '{"action":"left"}'
curl http://<pi-host>:3000/api/games/pacman/state
```

Run a game locally without matrix hardware:

```bash
python spotify_matrix.py --display-mode widget --widget-id core.pacman   --widget-dir store_widgets/core.pacman --mock-output data/frame.png   --game-input data/widgets/state/pacman-input.json   --game-state data/widgets/state/pacman-state.json
```

Games have sound: generated chiptune effects bundled per plugin, mixed so they
overlap, switched on under **Settings → Game sound**. See
[docs/game-audio.md](docs/game-audio.md).

High scores are saved. Any game with a score gets a persisted best, a top ten
and a play count with no code of its own, kept in `<data>/widgets/scores/` and
readable at `/api/games/<id>/scores`, so a best survives switching plugins and
rebooting.

Each game is also a plugin, so difficulty and rules are editable from its config
drawer: Pac-Man speed and lives, Snake walls, Breakout paddle width, Pong
opponent, and so on.

## Game controller

Pair a Bluetooth gamepad under **Settings → Bluetooth**, then turn it on under
**Settings → Game controller**. D-pad moves, **A** is the action button, **Start**
pauses, and the pad walks the plugin list when no game is running. It adapts to
whatever the running game declares, so one pad works everywhere. See
[docs/game-controller.md](docs/game-controller.md).

## Mini-joystick

A NULLLAB mini-joystick module (I2C 0x5A, one stick plus A/B/C/D/OK) can drive
the panel directly: it plays whichever game is running, and flicks through
plugins when none is. Enable it with:

```bash
curl -X POST http://<pi-host>:3000/api/joystick/config   -H "Content-Type: application/json" -d '{"config":{"enabled":true}}'
```

Wiring: **SDA to physical pin 3, SCL to physical pin 5**, V to 5V, G to ground.
Hardware I²C pins are fixed, so if you wired elsewhere either move the wires or
add a software bus with `dtoverlay=i2c-gpio`. **The module is 5V and the Pi's
GPIO is 3.3V — put a bidirectional level shifter on SDA and SCL.**

Stuck? **Settings → Mini-joystick → Detect module** scans every I²C bus and
tells you what is wrong. Full pin table, register map and button mapping in
[docs/mini-joystick.md](docs/mini-joystick.md).

## Legacy env support

The Python runtime still accepts environment variables if `data/config.json` is missing:

```text
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Direct auth through `spotify_matrix.py --auth-only` still works for local loopback redirects, but the FastAPI setup UI plus laptop helper is the recommended no-port-forwarding path.

### Bluetooth speakers

BlueZ holds the A2DP connection, but ALSA cannot see it without a bridge, so a
paired speaker is connected and silent until one is running. The container
installs `bluez-alsa-utils` and tries to start the daemon itself, and on most
setups that is all it takes.

It can fail with:

    Couldn't get BlueALSA PCM: The name org.bluealsa was not provided by any .service files

That is a D-Bus policy boundary rather than a missing package. Owning the name
`org.bluealsa` requires the policy in `/etc/dbus-1/system.d/bluealsa.conf`, and
the bus enforcing it is the Pi's, reached through the mapped socket - so it
reads the Pi's policy directory and never sees the copy inside the container.
Install the bridge on the Pi itself and it gets both the daemon and the policy
in the place the bus looks:

    sudo apt install bluez-alsa-utils
    sudo systemctl enable --now bluealsa

The container's ALSA plugin then talks to that daemon over the same socket, and
the speaker appears in Settings under Game sound, by name.

Do not select the bare `bluealsa` PCM by hand if you see it: it means device
`00:00:00:00:00:00` and fails with "PCM not found". The panel lists speakers by
address instead, and resolves an old saved setting to whichever is connected.
