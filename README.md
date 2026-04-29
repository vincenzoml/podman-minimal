# podman-minimal

Minimal launcher for rootless Podman with automatic GPU detection.

```bash
curl -fsSL https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/start.py | python3 - --install
```

## Prerequisites

- `podman`
- `python3`

## Quick usage

```bash
# Interactive shell (default image: nvidia/cuda ubuntu base)
./start.py

# Run command and exit
./start.py nvidia-smi

# Use local Dockerfile
./start.py --dockerfile /path/to/Dockerfile

# Use registry image
./start.py --image docker.io/library/ubuntu:24.04

# Use image archive
./start.py --image-file /path/to/image.tar
```

Dockerfile resolution order:

1. `--dockerfile PATH`
2. Launch directory: `Dockerfile`, `.devcontainers/Dockerfile`, `.devcontainers/dockerfile`, `.devcontainer/Dockerfile`, `.devcontainer/dockerfile`, `devcontainer/Dockerfile`, `devcontainer/dockerfile`
3. Script directory (same list as above)

### Dev Container layout and build context

If the Dockerfile lives under **`.devcontainer/`** or **`.devcontainers/`**, `start.py` uses the **parent directory** as the Podman/Docker **build context** (the directory you would pass as `.` after `-f`). That matches VS Code Dev Containers (`"build": { "context": ".." }` next to `"dockerfile"`). COPY paths in the Dockerfile must be expressed relative to that context (typically the repo root), not relative to `.devcontainer/` alone.

Heavy steps (`RUN`, unpacked dependencies) inside an image still **invalidate cache when inputs change**. In particular, **`COPY` steps** fingerprint the files copied from the context; edits there force those layers onward to rebuild—even if Dockerfile text unchanged.

### Default image tag, skipping `podman build`, and rebuilds

When you use the **default** base image and the launcher **auto-selects** a Dockerfile, the image tag is **`local/<build-folder>:<USERNAME>`**, where `<build-folder>` is the Dockerfile’s parent folder name normalized (leading dots stripped on names like `.devcontainer`).

**On each run:**

- If **`podman image exists`** that tag, **`podman build` is skipped** (no layer walk—you go straight to `podman run`). This is independent of Dockerfile-only hashing.
- **`--rebuild-image`** forces **`podman build`** even when the tag already exists. Use after you change Dockerfile or any **COPY** inputs that must be reflected in the image.
- **`--image myregistry/myimage:1.4.0`** (or bumping `:1.4.0` → `:1.5.0`) points at another tag entirely; paired with **`--dockerfile`** you get a reproducible stamp without overwriting the previous tag (`--rebuild-image` replaces the same tag).

`podman build` itself still relies on Podman/Docker layer cache for unchanged stages; omitting **`--rebuild-image`** avoids paying for the incremental “replay every step / check cache” pass when nothing about the resolved tag forces a rebuild.

## One-time setup

```bash
# Install global command (/usr/local/bin/podman-minimal); may prompt via sudo once
./start.py --install

# Optional: install system Quadlet bound to a fixed UID+dir
./start.py --install --uid 1001 --dir /srv/projects/topic-a --name topic-a --port 18080 --container-port 8080
```

Re-run `./start.py --install` anytime you update `start.py` and want the installed copy refreshed.

Create matching VS Code + `start.py` environment files in current directory:

```bash
./start.py --init-devcontainer
```

## Daemon (user systemd)

```bash
./start.py --daemon-install python3 -m http.server 8080
./start.py --daemon-status
./start.py --daemon-logs
./start.py --daemon-remove
```

`--daemon-install <cmd ...>` writes a user systemd unit that runs that exact command in a Podman container on login/boot and restarts it on failure.

Port mapping uses `--port HOST` and `--container-port CONTAINER` (default: same value if `--container-port` is omitted).

Daemon image selection uses the same Dockerfile/image rules as normal runs.

## Options (summary)

| Flag | Purpose |
|------|---------|
| `--dockerfile` | Path to Dockerfile |
| `--image` | Image name/tag to run (overrides auto tag) |
| `--image-file` | Load image from tarball via `podman load` |
| `--name`, `--port`, `--container-port` | Container name and port mapping |
| `--rebuild-image` | Run `podman build` even if the resolved tag exists |
| `--install`, `--uid`, `--dir` | Install launcher and optional system Quadlet |
| `--init-devcontainer` | Scaffold `.devcontainers` files |
| `--daemon-*` | User systemd daemon for a persistent container |

For the full flag list including daemon actions, run `./start.py --help`.
