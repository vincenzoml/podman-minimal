# podman-minimal

Run clean Podman dev/runtime environments from any folder with one command.

[GitHub repository](https://github.com/vincenzoml/podman-minimal)

If this saves you time, please ⭐ **star the repo**.

## Install (one-liners)

Only `python` is required. The launcher auto-installs Podman if missing.

### Linux (bash)

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

### macOS (zsh/bash)

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

### Windows (PowerShell)

```powershell
python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

## Minimal usage

```bash
podman-minimal
podman-minimal nvidia-smi
podman-minimal --dockerfile /path/to/Dockerfile
podman-minimal --image docker.io/library/ubuntu:24.04
podman-minimal --image-file /path/to/image.tar
```

## Use cases

- Interactive shell in a clean container without polluting your host.
- One-shot batch command execution.
- Per-repo isolated Podman workflow by copying `podman-minimal.py` into the project.
- Long-running service via user daemon mode (Linux).

## Setup / lifecycle

```bash
podman-minimal --version
podman-minimal --install
podman-minimal --install /opt/bin
podman-minimal --update
podman-minimal --uninstall
podman-minimal --uninstall /opt/bin
```

`--update` only works from an installed `podman-minimal` command and replaces the executable in place.

## Platform notes

- Linux: Podman auto-install via `apt-get`, `dnf`, `yum`, `zypper`, or `pacman`.
- macOS: auto-installs Homebrew when needed, then installs Podman via `brew`.
- Windows: installs Podman with `winget` (preferred) or `choco`.
- `--daemon-*` and system Quadlet install (`--install --uid --dir`) are Linux-only.
- The only system-wide file installed by default is `/usr/local/bin/podman-minimal`.

## More commands

```bash
podman-minimal --daemon-install python3 -m http.server 8080
podman-minimal --daemon-status
podman-minimal --daemon-logs
podman-minimal --daemon-remove
podman-minimal --init-devcontainer
podman-minimal --help
```

---

Built for fast, clean, reproducible local environments.  
If you like it, please ⭐ **star the repo**: [vincenzoml/podman-minimal](https://github.com/vincenzoml/podman-minimal)
# podman-minimal

Minimal launcher for rootless Podman with automatic GPU detection.

Only `python3` is required. `podman` is auto-installed when missing.

The only system-wide file installed is the command binary (default: `/usr/local/bin/podman-minimal`).

Platform auto-install layer:
- Linux: `apt-get`, `dnf`, `yum`, `zypper`, or `pacman` (with `sudo`).
- macOS: auto-installs Homebrew when missing, then installs `podman` via `brew`.
- Windows: uses `winget` (preferred) or `choco`.
- `--daemon-*` and system Quadlet setup are Linux-only.

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

# Update installed command in place from main branch
podman-minimal --update

# Optional: install system Quadlet bound to a fixed UID+dir
podman-minimal --install --uid 1001 --dir /srv/projects/topic-a --name topic-a --port 18080 --container-port 8080
```

Re-run `podman-minimal --install` anytime you update `podman-minimal.py` and want the installed copy refreshed.

`--update` works only from the installed `podman-minimal` command (not from repo `podman-minimal.py`) and replaces the executable in place. Existing running processes keep using the old code until restarted.

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
| `--update` | Update installed command in place from repo main branch |
| `--uid`, `--dir` | Optional system Quadlet inputs with `--install` |
| `--init-devcontainer` | Scaffold `.devcontainers` files |
| `--daemon-*` | User systemd daemon for a persistent container |

For the full flag list including daemon actions, run `podman-minimal --help`.
