# --- Web build stage: compile the React + MUI UI to static files ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SPOTIFY_MATRIX_DATA_DIR=/app/data \
    SPOTIFY_MATRIX_CONFIG=/app/data/config.json \
    SPOTIFY_TOKEN_CACHE=/app/data/spotify_token.json \
    PYTHON_BIN=python3

WORKDIR /app

# System build tools and fonts. Cached until this list changes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        alsa-utils \
        bluez \
        # BlueZ speaks A2DP but ALSA cannot hear it. bluez-alsa-utils is the
        # bridge: it runs a `bluealsa` daemon and adds a `bluealsa` PCM, which
        # is what makes a connected speaker appear as an output to choose.
        bluez-alsa-utils \
        build-essential \
        cmake \
        cython3 \
        dbus \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        fonts-noto-core \
        git \
        python3-dev \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=1.8,<2"

# --- Dependency layer -------------------------------------------------------
# Only pyproject.toml (and README, referenced by it) land here, so editing
# application code below does NOT invalidate the dependency install or the
# native matrix build. --no-root installs just the dependencies, not the
# project itself (the app runs from /app via PYTHONPATH, so it does not need
# to be pip-installed as a package).
COPY pyproject.toml README.md ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-root --no-ansi

# --- Native rpi-rgb-led-matrix build ----------------------------------------
# Depends only on the installed dependencies (Pillow headers), so it is cached
# across code changes and only rebuilds when dependencies change.
RUN PILLOW_VERSION="$(poetry run python -c 'import PIL; print(PIL.__version__)')" \
    && mkdir -p /tmp/pillow-src \
    && poetry run pip download --no-binary=:all: --no-deps "Pillow==${PILLOW_VERSION}" -d /tmp/pillow-src \
    && tar -xf /tmp/pillow-src/pillow-*.tar.gz -C /tmp/pillow-src \
    && PILLOW_HEADER="$(find /tmp/pillow-src -name Imaging.h | head -n 1)" \
    && test -n "${PILLOW_HEADER}" \
    && PILLOW_INCLUDE="$(dirname "${PILLOW_HEADER}")" \
    && echo "Using Pillow ${PILLOW_VERSION} header path: ${PILLOW_INCLUDE}" \
    && CFLAGS="-I${PILLOW_INCLUDE}" poetry run pip install --no-cache-dir git+https://github.com/hzeller/rpi-rgb-led-matrix \
    && rm -rf /tmp/pillow-src

# --- Application code --------------------------------------------------------
# Everything below rebuilds on a code change, but these are fast COPY layers;
# the expensive layers above stay cached.
COPY configs ./configs
COPY public ./public
COPY scripts ./scripts
COPY src ./src
COPY assistant_matrix_sdk ./assistant_matrix_sdk
COPY matrix_games ./matrix_games
COPY mini_joystick ./mini_joystick
COPY matrix_input ./matrix_input
COPY matrix_audio ./matrix_audio
COPY matrix_display ./matrix_display
COPY matrix_users ./matrix_users
# Bundled game apps, discovered at runtime alongside anything installed.
COPY store_apps ./store_apps
COPY store_server ./store_server
COPY spotify_matrix.py requirements.txt ./

# Built React UI (served at /app by FastAPI).
COPY --from=web /web/dist ./web-dist

RUN mkdir -p /app/data

ENV PYTHONPATH=/app

EXPOSE 3000

CMD ["poetry", "run", "python", "-m", "src.main"]
