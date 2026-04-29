# podman-minimal

Run clean Podman environments from any folder.

[Website](https://vincenzoml.github.io/podman-minimal/) · [Source](https://github.com/vincenzoml/podman-minimal) · [Issues](https://github.com/vincenzoml/podman-minimal/issues)

**Author:** Vincenzo Ciancia ([vincenzoml@gmail.com](mailto:vincenzoml@gmail.com))  
**License:** [GNU GPLv3 or later](LICENSE)

## Install

Linux / macOS:

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

Windows PowerShell:

```powershell
python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

User-local install:

```bash
mkdir -p ~/.local/bin
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install ~/.local/bin
```

## Usage

```bash
podman-minimal
podman-minimal nvidia-smi
podman-minimal --image docker.io/library/ubuntu:24.04 uname -a
podman-minimal --dockerfile /path/to/Dockerfile
podman-minimal --nohup run.log -- python3 -m http.server 8080
```

Default output is quiet: only Podman and your command speak. Use `-v` / `--verbose` for launcher details (version, image, Dockerfile, build context).

## Why not plain podman run?

- No-hassle bootstrap on Linux, macOS, and Windows.
- Runs with your same UID/GID (`keep-id`) and mounts your current working directory by default.
- Auto Dockerfile workflow: discover/build/reuse/pull without repeating boilerplate flags.
- VS Code-compatible devcontainer handling (`.devcontainer` / `.devcontainers` context behavior).
- Built-in convenience modes: `--nohup`, daemon helpers (Linux), quiet/verbose.

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
