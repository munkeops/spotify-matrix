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

RUN PIL_INCLUDE="$(poetry run python -c 'import pathlib, PIL; print(pathlib.Path(PIL.__file__).parent)')" \
    && echo "Using Pillow include path: ${PIL_INCLUDE}" \
    && CFLAGS="-I${PIL_INCLUDE}" poetry run pip install --no-cache-dir git+https://github.com/hzeller/rpi-rgb-led-matrix

RUN mkdir -p /app/data

ENV PYTHONPATH=/app

EXPOSE 3000

CMD ["poetry", "run", "python", "-m", "src.main"]
