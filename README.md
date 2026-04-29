# podman-minimal

Run clean Podman environments from any folder.

[Website](https://vincenzoml.github.io/podman-minimal/) · [Source](https://github.com/vincenzoml/podman-minimal) · [Issues](https://github.com/vincenzoml/podman-minimal/issues)

**Author:** Vincenzo Ciancia ([vincenzoml@gmail.com](mailto:vincenzoml@gmail.com))  
**License:** [GNU GPLv3 or later](LICENSE)

## Install

Linux / macOS:

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/refs/heads/main/podman-minimal.py').read().decode())" --install
```

Windows PowerShell:

```powershell
python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/refs/heads/main/podman-minimal.py').read().decode())" --install
```

User-local install:

```bash
mkdir -p ~/.local/bin
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/refs/heads/main/podman-minimal.py').read().decode())" --install ~/.local/bin
```

## Usage

```bash
podman-minimal
podman-minimal --image docker.io/library/debian:12 uname -a
podman-minimal --dockerfile /path/to/Dockerfile
podman-minimal --root --image docker.io/library/ubuntu:26.04 bash
podman-minimal --host-root --image docker.io/library/ubuntu:26.04 ls /host
podman-minimal --nohup run.log -- python3 -m http.server 8080
```

Default output is quiet: only Podman and your command speak. Use `-v` / `--verbose` for launcher details (version, image, Dockerfile, build context).

## Default image

- Default base image: `docker.io/library/ubuntu:26.04`.
- If you run `podman-minimal` without `--image` and no local Dockerfile is discovered, this Ubuntu 26.04 image is pulled (once) and reused.
- You can always override it per run with `--image`, for example:

```bash
podman-minimal --image docker.io/library/ubuntu:24.04 bash -lc "cat /etc/os-release"
```

## Useful base images (well-known)

These are common, broadly useful defaults for different workflows:

- `docker.io/library/ubuntu:26.04`  
  General-purpose Ubuntu userland; good default for shell tools and apt-based workflows.
- `docker.io/library/debian:12`  
  Stable, conservative base for CI-style reproducibility and server-side utilities.
- `docker.io/library/python:3.12-slim`  
  Ready-to-use Python runtime with a smaller footprint than full distro images.
- `docker.io/library/node:22-bookworm`  
  Good starting point for JavaScript/TypeScript development and build tooling.
- `docker.io/library/golang:1.23`  
  Complete Go toolchain image for compiling and testing Go projects.
- `docker.io/library/rust:1.89`  
  Includes Rust toolchain and Cargo; useful for Rust build/test loops.

Example overrides:

```bash
podman-minimal --image docker.io/library/python:3.12-slim python -V
podman-minimal --image docker.io/library/node:22-bookworm node -v
podman-minimal --image docker.io/library/golang:1.23 go version
podman-minimal --image docker.io/library/rust:1.89 rustc --version
```

## Why not plain podman run?

- No-hassle bootstrap on Linux, macOS, and Windows.
- Runs with your same UID/GID (`keep-id`) and mounts your current working directory by default.
- Auto Dockerfile workflow: discover/build/reuse/pull without repeating boilerplate flags.
- VS Code-compatible devcontainer handling (`.devcontainer` / `.devcontainers` context behavior).
- Built-in convenience modes: `--nohup`, daemon helpers (Linux), quiet/verbose.

## Mount behavior

- Interactive shell and batch command runs mount only your current working directory by default.
- The launcher does not mount your whole home directory by default.
- Use `--host-root` to also mount the host root filesystem read-only at `/host` when you need to inspect the full host layout.

```bash
podman-minimal --host-root -- bash -lc "ls /host && ls /host/Users"
```

## Root mode inside container

- Default behavior runs as your host UID/GID (`keep-id`), not as container root.
- Use `--root` to run interactive shells and batch commands as container root.
- This is the easiest way to install packages in the default Ubuntu image:

```bash
podman-minimal --root -- bash -lc "apt-get update && apt-get install -y sudo"
```

- `sudo` is often not installed in minimal images; in root mode you usually do not need `sudo` at all.
- `su -` also depends on tools/users present in the image. Root mode avoids that dependency for admin tasks.

## Lifecycle

```bash
podman-minimal --version
podman-minimal --install [DIR]
podman-minimal --update
podman-minimal --uninstall [DIR]
```

## Safety

- Normal runs do not use `sudo`.
- `--install`, `--update`, and `--uninstall` write/remove only the `podman-minimal` executable.
- Existing symlink targets are not overwritten during normal install/update; writes use atomic replace.
- Protected install paths may require `sudo`; use `--install ~/.local/bin` to avoid that.
- Set `PODMAN_MINIMAL_NO_SUDO=1` to forbid this script from invoking `sudo`.
- If Podman is missing, the script can use the normal platform installer: `apt/dnf/yum/zypper/pacman` on Linux, Homebrew on macOS, `winget`/`choco` on Windows.

## Dockerfiles

Resolution order:

1. `--dockerfile PATH`
2. Current directory: `Dockerfile`, `.devcontainers/Dockerfile`, `.devcontainer/Dockerfile`, `devcontainer/Dockerfile` (case variants included)
3. Same list next to the script

For `.devcontainer/` and `.devcontainers/`, the build context is the parent directory.

## Linux daemon

```bash
podman-minimal --daemon-install python3 -m http.server 8080
podman-minimal --daemon-status
podman-minimal --daemon-logs
podman-minimal --daemon-remove
```

System Quadlet is explicit and root-only:

```bash
sudo podman-minimal --install --uid 1001 --dir /srv/project --name project
```

## Other

```bash
podman-minimal --init-devcontainer
podman-minimal --help
```

Copyright © 2026 Vincenzo Ciancia.
