# Not built in the sandbox (no Docker daemon); tests/test_docker_files.py reads
# these files as text. The sizes in ANALYSIS.md come
# from a venv measured with pip. Build from the repo root:
#   docker build -f docker/Dockerfile -t memorymap .
#
# Two variants from one file: the default has no built-in search model (the
# deterministic engine, FTS5 search, an Ollama embedder on the host);
# --build-arg WITH_EMBEDDER=1 adds fastembed and ONNX Runtime (about +120 MB
# installed; the model itself, 67 MB, downloads after a yes in the app).
FROM python:3.13-slim AS build
ARG WITH_EMBEDDER=0
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt pyproject.toml ./
# requirements.txt lists fastembed, which pulls ONNX Runtime. The default
# image filters it out; the embedder build keeps it.
RUN python -m venv /venv \
 && if [ "$WITH_EMBEDDER" = "1" ]; then \
      /venv/bin/pip install -r requirements.txt; \
    else \
      grep -vE '^(fastembed|pytest|httpx)' requirements.txt > /tmp/req.txt \
      && /venv/bin/pip install -r /tmp/req.txt; \
    fi
COPY src ./src
COPY frontend ./frontend
COPY migrations ./migrations
COPY alembic.ini ./
RUN /venv/bin/pip install --no-deps -e .

FROM python:3.13-slim
RUN useradd --create-home --uid 1000 mm \
 && mkdir -p /data /models \
 && chown mm:mm /data /models
COPY --from=build /venv /venv
COPY --from=build /app /app
WORKDIR /app
# One volume holds everything the person owns: the database, attachments, the
# LAN certificate, backups. Models live in a second volume so an upgrade or a
# reset of the notebook never re-downloads gigabytes.
ENV PATH=/venv/bin:$PATH \
    PYTHONPATH=/app/src \
    TESSELLATE_DATA_DIR=/data \
    HF_HOME=/models/hf \
    OLLAMA_URL=http://host.docker.internal:11434
VOLUME ["/data", "/models"]
EXPOSE 8000 8443
USER mm
# TESSELLATE_BIND widens the bind inside the container (the bridge is not
# loopback) and TESSELLATE_FIRST_PASSWORD seeds a password when none is set.
# Publish the port on the host's loopback (compose.yaml) and put TLS in front
# for other devices. Behind a proxy that forwards its own name, list it in
# TESSELLATE_ALLOWED_HOSTS (comma-separated, names only) or the app answers 421.
ENV TESSELLATE_BIND=0.0.0.0 \
    TESSELLATE_PORT=8000
CMD ["python", "-m", "tessellate"]
