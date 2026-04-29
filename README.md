# podman-minimal

Minimal launcher for rootless Podman with automatic GPU detection.

Only `python3` is required. `podman` is auto-installed when missing. 

The only system-wide file installed is the command binary (default: `/usr/local/bin/podman-minimal`).

To install run this:

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

## Minimal usage

```bash
# Interactive shell (default image: nvidia/cuda ubuntu base)
podman-minimal

# Run command and exit
podman-minimal nvidia-smi

# Use local Dockerfile
podman-minimal --dockerfile /path/to/Dockerfile

# Use registry image
podman-minimal --image docker.io/library/ubuntu:24.04

# Use image archive
podman-minimal --image-file /path/to/image.tar
```

## Use cases

- Interactive shell: launch a clean container shell without polluting the host.
- Batch command: run one command and exit.
- Repo/folder local VM-style project: copy `podman-minimal.py` into a repo and keep an isolated Podman workflow per project.
- Daemon mode: run persistent services with user systemd.

### Dev Container layout and build context

If the Dockerfile lives under **`.devcontainer/`** or **`.devcontainers/`**, `podman-minimal.py` uses the **parent directory** as the Podman/Docker **build context**. That matches VS Code Dev Containers (`"build": { "context": ".." }` next to `"dockerfile"`). COPY paths in the Dockerfile must be relative to that context (typically the repo root), not just `.devcontainer/`.

Dockerfile resolution order:

1. `--dockerfile PATH`
2. Launch directory: `Dockerfile`, `.devcontainers/Dockerfile`, `.devcontainers/dockerfile`, `.devcontainer/Dockerfile`, `.devcontainer/dockerfile`, `devcontainer/Dockerfile`, `devcontainer/dockerfile`
3. Script directory (same list as above)

### Default image tag, skipping `podman build`, and rebuilds

When you use the default base image and the launcher auto-selects a Dockerfile, the image tag is `local/<build-folder>:<USERNAME>`.

On each run:

- If `podman image exists` for that tag, `podman build` is skipped.
- `--rebuild-image` forces `podman build` even if the tag already exists.
- `--image myregistry/myimage:1.4.0` uses that tag directly.

## One-time setup

```bash
# Install command (default dir: /usr/local/bin). Tries direct write first, falls back to sudo only if needed.
podman-minimal --install

# Install to a custom directory
podman-minimal --install /opt/bin

# Uninstall from default directory
podman-minimal --uninstall

# Uninstall from a custom directory
podman-minimal --uninstall /opt/bin

# Optional: install system Quadlet bound to a fixed UID+dir
podman-minimal --install --uid 1001 --dir /srv/projects/topic-a --name topic-a --port 18080 --container-port 8080
```

Re-run `podman-minimal --install` anytime you update `podman-minimal.py` and want the installed copy refreshed.

Create matching VS Code + `podman-minimal.py` environment files in current directory:

```bash
podman-minimal --init-devcontainer
```

## Daemon (user systemd)

```bash
podman-minimal --daemon-install python3 -m http.server 8080
podman-minimal --daemon-status
podman-minimal --daemon-logs
podman-minimal --daemon-remove
```

`--daemon-install <cmd ...>` writes a user systemd unit that runs that command in a Podman container on login/boot and restarts it on failure.

Port mapping uses `--port HOST` and `--container-port CONTAINER` (default: same value if `--container-port` is omitted).

## Options (summary)

| Flag | Purpose |
|------|---------|
| `--dockerfile` | Path to Dockerfile |
| `--image` | Image name/tag to run (overrides auto tag) |
| `--image-file` | Load image from tarball via `podman load` |
| `--name`, `--port`, `--container-port` | Container name and port mapping |
| `--rebuild-image` | Run `podman build` even if the resolved tag exists |
| `--install [DIR]`, `--uninstall [DIR]` | Install/remove command in DIR (default `/usr/local/bin`) |
| `--uid`, `--dir` | Optional system Quadlet inputs with `--install` |
| `--init-devcontainer` | Scaffold `.devcontainers` files |
| `--daemon-*` | User systemd daemon for a persistent container |

For the full flag list including daemon actions, run `podman-minimal --help`.
