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
        git \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=1.8,<2"

COPY pyproject.toml ./
COPY README.md ./
COPY configs ./configs
COPY public ./public
COPY scripts ./scripts
COPY src ./src
COPY spotify_matrix.py requirements.txt ./

RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-ansi

RUN git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix /tmp/rpi-rgb-led-matrix \
    && cd /tmp/rpi-rgb-led-matrix/bindings/python \
    && MATRIX_PYTHON="$(cd /app && poetry env info --executable)" \
    && make build-python PYTHON="${MATRIX_PYTHON}" \
    && make install-python PYTHON="${MATRIX_PYTHON}" \
    && rm -rf /tmp/rpi-rgb-led-matrix

RUN mkdir -p /app/data

ENV PYTHONPATH=/app

EXPOSE 3000

CMD ["poetry", "run", "python", "-m", "src.main"]
