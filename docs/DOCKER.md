# Run Tessellate in Docker

For a server or a NAS. Tessellate is designed to pair with a local AI model (Ollama, LM Studio or llama.cpp recommended) but works without one: capture, search by keyword, documents and boards need no model.

The files are `docker/Dockerfile` and `docker/compose.yaml`. The image was not built when this guide was written: the machine had a Docker client but no running daemon. The commands and variables below were checked against the files and the code, not against a first build. Report what your first build says.

## Quick start

From the repository root:

```
TESSELLATE_FIRST_PASSWORD=choose-a-long-one docker compose -f docker/compose.yaml up -d --build
```

Open `http://localhost:8000` and sign in with that password. `TESSELLATE_FIRST_PASSWORD` is used only while the notebook has no password, is never logged, and is dropped from the process once read. After the first start, stop passing it: the password lives in the notebook.

Logs: `docker compose -f docker/compose.yaml logs -f`. Stop: `docker compose -f docker/compose.yaml down` (volumes are kept).

## Where the data lives

Two named volumes, set in `compose.yaml`:

| Volume | In the container | Holds |
| --- | --- | --- |
| `memorymap-data` | `/data` | Database, uploads, the LAN certificate, backups |
| `memorymap-models` | `/models` | Downloaded embedding and OCR models (`HF_HOME`) |

Compose prefixes the volume names with the project name (the folder, `docker` here), so list them with `docker volume ls`.

**Back up** the notebook by either route:

- In the app: Settings, Import & export, Export full backup (a portable zip).
- From the host, a copy of the volume (stop the container first so the database is quiet):

```
docker compose -f docker/compose.yaml stop
docker run --rm -v docker_memorymap-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/tessellate-data.tgz -C /data .
docker compose -f docker/compose.yaml start
```

Check the volume name with `docker volume ls` first. To restore, extract the archive into an empty volume the same way.

`docker compose down -v` deletes the volumes, and your notes with them.

## Port and network exposure

`compose.yaml` publishes `127.0.0.1:8000:8000`: reachable from the Docker host only. Inside the container `TESSELLATE_BIND=0.0.0.0` (the bridge is not loopback), which is why the loopback publish matters.

**LAN caveat.** Changing the mapping to `8000:8000` puts the notebook, over plain http, on every network the host is on. Do not do that. For other devices, keep the loopback publish and put a reverse proxy with TLS (Caddy, nginx, Traefik) in front. Then set `TESSELLATE_ALLOWED_HOSTS` to the public name the proxy forwards (`notes.example.com`, several comma-separated, names only), or the app answers 421. The "Allow other devices" switch does not apply in a container; use the port mapping and the proxy instead. Set a strong password before you expose it at all.

## Environment variables

Those the image or compose file sets, and the ones the code reads that make sense in a container.

| Variable | Default in the image | What it does |
| --- | --- | --- |
| `TESSELLATE_DATA_DIR` | `/data` | Where the notebook lives |
| `TESSELLATE_BIND` | `0.0.0.0` | Address the server binds inside the container (unset elsewhere: `127.0.0.1`) |
| `TESSELLATE_PORT` | `8000` | Port inside the container; change the mapping to match |
| `TESSELLATE_FIRST_PASSWORD` | unset (compose passes it through from your shell) | Seeds a password while none is set |
| `TESSELLATE_ALLOWED_HOSTS` | unset (compose passes it through) | Host names a reverse proxy forwards |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Where Ollama is |
| `HF_HOME` | `/models/hf` | Model cache, on the models volume |
| `TESSELLATE_RAM_GB` | detected | Overrides the memory the app thinks it has; set it if a container limit is lower than the host's |
| `TESSELLATE_EMBED_THREADS` | `1` | Threads for the built-in search model |
| `TESSELLATE_LAN_PORT` | `8443` | HTTPS port for LAN mode; not used in a container |

The default image has no built-in search engine (search by keyword, plus an Ollama embedder). `--build-arg WITH_EMBEDDER=1` (or `WITH_EMBEDDER: "1"` in compose) adds fastembed and ONNX Runtime, about 120 MB more; the model (67 MB) downloads after a yes in the app.

## Connect a model server on the host

The model server runs on the host, not in the container. `compose.yaml` already maps `host.docker.internal` to the host (`extra_hosts: host-gateway`, which Linux needs).

| Server | Address from the container | Notes |
| --- | --- | --- |
| Ollama | `http://host.docker.internal:11434` (the `OLLAMA_URL` default) | Make Ollama listen beyond loopback: `OLLAMA_HOST=0.0.0.0` |
| LM Studio | `http://host.docker.internal:1234/v1` | Turn on "Serve on local network" |
| llama.cpp `llama-server` | `http://host.docker.internal:8080/v1` | Start it with `--host 0.0.0.0` |

For Ollama nothing else is needed. For LM Studio and llama.cpp, open Settings, Models, Model backend, pick "LM Studio / llama.cpp / Jan / vLLM", enter the address (ending `/v1`) and press Connect. The "Keep Atlas on this machine" switch accepts addresses on your own network, which includes the host. A server on another machine works the same way with its LAN address. Which model suits your hardware is in [MODELS.md](MODELS.md).

A host firewall may block the Docker bridge from reaching those ports; allow the bridge subnet if Connect fails.

## Updating

```
git pull
docker compose -f docker/compose.yaml up -d --build
```

The volumes are reused, so the notebook and downloaded models stay. Take a backup first; the app migrates the database on start.

## Troubleshooting

- **421 Misdirected Request:** you reached it by a name the app does not know. Add the name to `TESSELLATE_ALLOWED_HOSTS`.
- **Cannot reach it from another device:** by design, the port is loopback only. See the network section.
- **Model not found or Connect fails:** from inside the container, `localhost` is the container. Use `host.docker.internal`, and check the server listens beyond loopback.
- **On Linux, `host.docker.internal` does not resolve:** keep the `extra_hosts` line in `compose.yaml`.
- **Locked out:** `docker compose -f docker/compose.yaml exec memorymap python -m tessellate --reset-password` clears the password (private notes stay sealed), then set a new one with `TESSELLATE_FIRST_PASSWORD` on the next start.
- **Permission error on `/data`:** the container runs as uid 1000 (`mm`). If you swap the volume for a bind mount, `chown 1000:1000` the folder.
- **Not available in a container:** the desktop window and tray, native file dialogs, and shortcuts.

More fixes are in [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and the shorter Docker note in [INSTALL.md](INSTALL.md#docker).
