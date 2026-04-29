# podman-minimal

Run clean Podman dev/runtime environments from any folder with one command. Rootless `podman run` is the normal path: your workloads stay in containers, not on the host.

[GitHub repository](https://github.com/vincenzoml/podman-minimal)  
[Project website (GitHub Pages)](https://vincenzoml.github.io/podman-minimal/)

**Author:** Vincenzo Ciancia ([vincenzoml@gmail.com](mailto:vincenzoml@gmail.com))  
**Copyright © 2026 Vincenzo Ciancia.** Licensed under the [GNU General Public License v3.0 or later](LICENSE) (GPLv3+).

**This project is free software.** If it helps you, a ⭐ star on GitHub is a simple way to show appreciation and helps others find it.

---

## Install (one-liners)

You only need Python. If Podman is missing, the launcher can install it after an explicit interactive confirmation (see [Sudo and safety](#sudo-and-safety)).

### Linux / macOS

```bash
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

### Windows (PowerShell)

```powershell
python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install
```

Default install location is `podman-minimal` under `/usr/local/bin`. To **avoid sudo** for installation, use a directory you own and ensure it is on your `PATH`:

```bash
mkdir -p ~/.local/bin
python3 -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/podman-minimal.py').read().decode())" --install ~/.local/bin
```

---

## Minimal usage

```bash
podman-minimal                              # interactive shell
podman-minimal nvidia-smi                   # run one command
podman-minimal --dockerfile /path/to/Dockerfile
podman-minimal --image docker.io/library/ubuntu:24.04
podman-minimal --image-file /path/to/image.tar
podman-minimal --nohup run.log -- python3 -m http.server 8080   # detached + log + console mirror
podman-minimal --help
```

Use `--` before the command when passing flags to the inner command, e.g. `podman-minimal -- myapp --verbose`.

---

## Quiet vs verbose (`-v` / `--verbose`)

| Mode | What you see |
|------|----------------|
| **Default** | Only output from Podman and from the command you run (and errors). No launcher chatter. |
| **Verbose** | Same, plus launcher messages: version, hint to use `--update`, resolved **image**, **Dockerfile** and **build context** when relevant, build/skip messages, etc. |

```bash
podman-minimal -v -- python3 -c "print('hello')"
```

---

## Setup and lifecycle

| Command | Purpose |
|---------|---------|
| `--version` | Print version and exit. |
| `--install [DIR]` | Install `podman-minimal` into `DIR` (default `/usr/local/bin`). Writes **only** that single executable; tries without elevated privileges first, uses `sudo` only if the path is not writable. |
| `--uninstall [DIR]` | Remove that executable from `DIR` (same default). Uses `sudo` only if removal fails without it. |
| `--update` | Re-download from `main` and replace the **installed** `podman-minimal` in place. Does **not** apply to running from `podman-minimal.py` in a repo. Already-running processes keep the old code until restarted. |
| `--nohup [LOGFILE]` | Run **command mode** detached (survives closing the terminal). Appends to `LOGFILE` (default `podman-minimal.nohup.log`) and mirrors new lines to the console while it is still open. Requires a command after `--`. |

```bash
podman-minimal --version
podman-minimal --install
podman-minimal --install ~/.local/bin
podman-minimal --update
podman-minimal --uninstall
podman-minimal --uninstall ~/.local/bin
```

---

## Sudo and safety

The launcher is designed to **not** require elevated privileges for everyday container runs. Administrator prompts appear only in these situations:

| Situation | Behavior |
|-----------|----------|
| **Normal run** (shell, `podman run`, etc.) | No `sudo` from this script. |
| **`--install` / `--uninstall` / `--update`** | Writes only the `podman-minimal` binary. Unprivileged write/removal is tried first; **`sudo` is used only if** the target path is protected. Missing privileged directories are **not** created with `sudo`; create them yourself or use `--install ~/.local/bin`. |
| **Auto-install Podman (Linux)** | Asks first, then uses your distro package manager **with** `sudo`. Install Podman yourself first if you do not want that. |
| **Auto-install Podman (macOS)** | Asks first. If Homebrew is missing, it runs the official Homebrew installer; then asks/uses `brew install podman`. |
| **Auto-install Podman (Windows)** | Asks first, then uses `winget` or `choco` (elevation is handled by those tools). |
| **`--daemon-install`** | May use **`sudo`** once for `loginctl enable-linger` if linger is not already enabled. |
| **`--install --uid … --dir …`** (Quadlet) | Requires **root on Linux**; writes under `/etc/containers/systemd`. If not root, it aborts before installing the command to avoid partial setup. Opt-in only. |

**Opt out of `sudo` from this script:** set `PODMAN_MINIMAL_NO_SUDO=1`. Then any step that would require `sudo` fails with a clear error instead of invoking it (install Podman and pick a user-writable `--install` path yourself).

```bash
export PODMAN_MINIMAL_NO_SUDO=1
podman-minimal --install ~/.local/bin   # ok if writable
```

Canceling a password prompt aborts that step; the script does not bypass your approval.

For automation where you intentionally want package-manager installs without an interactive confirmation, set `PODMAN_MINIMAL_ASSUME_YES=1`. This does **not** bypass `sudo`, `winget`, `choco`, Homebrew, or OS-level approval prompts.

---

## Dockerfile discovery and build context

**Resolution order**

1. `--dockerfile PATH`
2. Current directory: `Dockerfile`, `.devcontainers/Dockerfile`, `.devcontainers/dockerfile`, `.devcontainer/Dockerfile`, `.devcontainer/dockerfile`, `devcontainer/Dockerfile`, `devcontainer/dockerfile`
3. Same list relative to the script directory

If the Dockerfile lives under **`.devcontainer/`** or **`.devcontainers/`**, the **parent directory** is used as the Podman **build context** (same idea as VS Code Dev Containers `build.context`: `".."`). `COPY` paths must be relative to that context (usually repo root), not only to `.devcontainer/`.

**Default image tag** (when using the default base image and an auto-selected Dockerfile): `local/<build-folder>:<USERNAME>`. If that image already exists, `podman build` is skipped unless you pass `--rebuild-image`.

---

## User daemon (Linux only)

```bash
podman-minimal --daemon-install python3 -m http.server 8080
podman-minimal --daemon-status
podman-minimal --daemon-logs
podman-minimal --daemon-remove
```

`--port` / `--container-port` control host ↔ container port mapping for daemon mode. `--daemon-*` is **not** supported on macOS or Windows (use `--nohup` or your own service manager there).

**Optional system Quadlet** (Linux, root): `--install --uid UID --dir PROJECT_DIR` together with `--name`, `--port`, etc. installs a system unit under `/etc/containers/systemd`. This is separate from the single-file `podman-minimal` install.

---

## Scaffold dev container files

```bash
podman-minimal --init-devcontainer
```

Creates `.devcontainers/Dockerfile` and `devcontainer.json` in the current directory when missing.

---

## Platform summary

- **Linux:** GPU-friendly defaults; Podman install via `apt-get`, `dnf`, `yum`, `zypper`, or `pacman` after confirmation (with `sudo` unless Podman is already installed or `PODMAN_MINIMAL_NO_SUDO=1`).
- **macOS:** Homebrew installed if missing after confirmation, then `brew install podman`.
- **Windows:** `winget` preferred, else `choco`, after confirmation.

---

## Options (quick reference)

| Flag | Purpose |
|------|---------|
| `-v`, `--verbose` | Launcher diagnostics (image, Dockerfile, build hints). |
| `--version` | Print version. |
| `--install [DIR]` | Install command into `DIR`. |
| `--uninstall [DIR]` | Remove command from `DIR`. |
| `--update` | Refresh installed binary from `main`. |
| `--nohup [LOGFILE]` | Detached command + log + console mirror. |
| `--dockerfile`, `--image`, `--image-file` | Image/build inputs. |
| `--name`, `--port`, `--container-port` | Container name and ports. |
| `--rebuild-image` | Force `podman build` even if tag exists. |
| `--init-devcontainer` | Scaffold `.devcontainers`. |
| `--daemon-install`, `--daemon-remove`, `--daemon-status`, `--daemon-logs` | User systemd daemon (Linux). |
| `--uid`, `--dir` | With `--install`: optional system Quadlet (Linux, root). |

Run `podman-minimal --help` for the full list.

---

## Use cases

- **Interactive shell** in a clean environment without installing packages on the host.
- **Batch** one-off commands in the same image/work tree.
- **Per-repo workflow** by keeping `podman-minimal.py` in the project.
- **Long-running jobs** with `--nohup` (any OS) or `--daemon-install` (Linux).

---

## License

Copyright © 2026 [Vincenzo Ciancia](mailto:vincenzoml@gmail.com).

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version**.

See the [`LICENSE`](LICENSE) file for the full GPLv3 text.
