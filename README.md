# podman-minimal

Minimal launcher for rootless Podman with automatic GPU detection.

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
1) `--dockerfile PATH`
2) Launch directory: `Dockerfile`, `.devcontainer/Dockerfile`, `.devcontainer/dockerfile`, `devcontainer/Dockerfile`, `devcontainer/dockerfile`
3) Script directory (same list as above)

## One-time setup

```bash
# Install global command (/usr/local/bin/podman-minimal)
./start.py --install

# Optional: install system Quadlet bound to a fixed UID+dir
./start.py --install --uid 1001 --dir /srv/projects/topic-a --name topic-a --port 18080 --container-port 8080
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

## Options

`--dockerfile`, `--image`, `--image-file`, `--name`, `--port`, `--container-port`, `--install`, `--daemon-install`, `--daemon-status`, `--daemon-logs`, `--daemon-remove`, `--uid`, `--dir`
