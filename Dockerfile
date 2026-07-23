FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SPOTIFY_MATRIX_DATA_DIR=/app/data \
    SPOTIFY_MATRIX_CONFIG=/app/data/config.json \
    SPOTIFY_TOKEN_CACHE=/app/data/spotify_token.json \
    PYTHON_BIN=python3

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        cython3 \
        fonts-noto-core \
        git \
        python3-dev \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=1.8,<2"

COPY pyproject.toml ./
COPY README.md ./
COPY configs ./configs
COPY public ./public
COPY scripts ./scripts
COPY src ./src
COPY assistant_matrix_sdk ./assistant_matrix_sdk
COPY spotify_matrix.py requirements.txt ./

RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-ansi

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

RUN mkdir -p /app/data

ENV PYTHONPATH=/app

EXPOSE 3000

CMD ["poetry", "run", "python", "-m", "src.main"]
