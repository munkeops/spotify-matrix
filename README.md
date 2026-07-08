# Spotify Matrix

Shows the current Spotify album art on a 64x64 RGB matrix as a circular record. The album art is cropped to a disk, spun while Spotify reports playback as active, and left stopped at the current angle when paused.

The project now uses a Python-only stack:

- FastAPI setup service in `src/`
- Static HTML/CSS/JS UI in `public/`
- Python OAuth helper in `scripts/oauth_helper.py`
- Runtime display script in `spotify_matrix.py`
- TOML service config in `configs/base_config.toml`

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
   http://127.0.0.1/callback
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

## Legacy env support

The Python runtime still accepts environment variables if `data/config.json` is missing:

```text
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Direct auth through `spotify_matrix.py --auth-only` still works for local loopback redirects, but the FastAPI setup UI plus laptop helper is the recommended no-port-forwarding path.
