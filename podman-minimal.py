#!/usr/bin/env python3
# Copyright (C) 2026 Vincenzo Ciancia <vincenzoml@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Minimal Podman launcher with optional root Quadlet installer."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import re
import tempfile
import platform
import time
import getpass
from urllib.request import urlopen
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    import pwd
    import grp
except ImportError:
    pwd = None
    grp = None


DEFAULT_IMAGE = "docker.io/nvidia/cuda:12.4.1-base-ubuntu22.04"
DEFAULT_PORT = 18080
VERSION = "1.0"
DEFAULT_INSTALL_DIR = "/usr/local/bin"
COMMAND_NAME = "podman-minimal"
SYSTEM_OCI_DIR = "/etc/containers/systemd"
RAW_START_PY_URL = "https://raw.githubusercontent.com/vincenzoml/podman-minimal/refs/heads/main/podman-minimal.py"
VERBOSE = False
DEFAULT_NOHUP_LOG = "podman-minimal.nohup.log"
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def sudo_allowed() -> bool:
    """If PODMAN_MINIMAL_NO_SUDO is set (1/true/yes), never invoke sudo — safer on shared machines."""
    val = os.environ.get("PODMAN_MINIMAL_NO_SUDO", "").strip().lower()
    return val not in ("1", "true", "yes", "on")


def assume_yes() -> bool:
    val = os.environ.get("PODMAN_MINIMAL_ASSUME_YES", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def confirm_host_change(message: str) -> None:
    """Ask before package-manager or installer operations that modify the host."""
    if assume_yes():
        return
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"{message} Refusing to continue without an interactive terminal. "
            "Install the dependency yourself or set PODMAN_MINIMAL_ASSUME_YES=1."
        )
    answer = input(f"{message} Continue? [Y/n] ").strip().lower()
    if answer not in ("", "y", "yes"):
        raise RuntimeError("Cancelled by user.")


def require_sudo_capability(explanation: str) -> None:
    if not sudo_allowed():
        raise RuntimeError(
            f"{explanation} "
            "Set PODMAN_MINIMAL_NO_SUDO=0 (or unset it) to allow sudo, "
            "or use a user-writable install path (e.g. ~/.local/bin) and install Podman yourself."
        )
    ensure_command_exists("sudo")


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True)


def run_capture(cmd: List[str], check: bool = True) -> str:
    proc = subprocess.run(cmd, check=check, text=True, capture_output=True)
    return proc.stdout.strip()


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path = path.expanduser()
    parent = path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    if not parent.is_dir():
        raise RuntimeError(f"Parent path is not a directory: {parent}")
    if path.exists() and path.is_dir():
        raise RuntimeError(f"Refusing to replace directory: {path}")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        if hasattr(os, "O_DIRECTORY"):
            try:
                dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            except OSError:
                dir_fd = None
            if dir_fd is not None:
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
    finally:
        tmp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str, mode: int | None = None) -> None:
    atomic_write(path, text.encode("utf-8"), mode=mode)


def validate_name(value: str, label: str = "name") -> str:
    if not SAFE_NAME_RE.fullmatch(value):
        raise RuntimeError(
            f"Invalid {label}: {value!r}. Use letters, digits, '.', '_' or '-', starting with a letter or digit."
        )
    return value


def ensure_command_exists(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def vprint(message: str) -> None:
    if VERBOSE:
        print(message)


def infoprint(message: str) -> None:
    print(message)


def host_os() -> str:
    name = platform.system().lower()
    if name == "darwin":
        return "macos"
    if name == "windows":
        return "windows"
    return "linux"


def install_homebrew_if_missing() -> None:
    if shutil.which("brew"):
        return
    confirm_host_change("Homebrew is missing; podman-minimal can run the official Homebrew installer.")
    eprint("Installing Homebrew via the official installer...")
    run(
        [
            "/bin/bash",
            "-c",
            "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
        ]
    )


def install_podman_if_missing() -> None:
    if shutil.which("podman") is not None:
        return
    os_name = host_os()
    eprint("Podman not found.")
    if os_name == "linux":
        confirm_host_change("podman-minimal can install Podman with your Linux package manager using sudo.")
        require_sudo_capability("Automatic Podman install on Linux uses sudo with your package manager.")
        installers: List[List[str]] = []
        if shutil.which("apt-get"):
            installers = [
                ["sudo", "apt-get", "update"],
                ["sudo", "apt-get", "install", "-y", "podman"],
            ]
        elif shutil.which("dnf"):
            installers = [["sudo", "dnf", "install", "-y", "podman"]]
        elif shutil.which("yum"):
            installers = [["sudo", "yum", "install", "-y", "podman"]]
        elif shutil.which("zypper"):
            installers = [["sudo", "zypper", "--non-interactive", "install", "podman"]]
        elif shutil.which("pacman"):
            installers = [["sudo", "pacman", "-S", "--noconfirm", "podman"]]
        if not installers:
            raise RuntimeError(
                "Podman is missing and no supported Linux package manager was detected "
                "(supported: apt-get, dnf, yum, zypper, pacman)."
            )
        eprint(f"Running: {' && '.join(' '.join(cmd) for cmd in installers)}")
        for cmd in installers:
            run(cmd)
    elif os_name == "macos":
        install_homebrew_if_missing()
        brew_bin = shutil.which("brew")
        if not brew_bin:
            raise RuntimeError("Homebrew installation did not succeed. Install Podman manually.")
        confirm_host_change("podman-minimal can install Podman with Homebrew.")
        eprint("Running: brew install podman")
        run([brew_bin, "install", "podman"])
    elif os_name == "windows":
        if shutil.which("winget"):
            confirm_host_change("podman-minimal can install Podman with winget.")
            eprint("Running: winget install -e --id RedHat.Podman")
            run(["winget", "install", "-e", "--id", "RedHat.Podman"])
        elif shutil.which("choco"):
            confirm_host_change("podman-minimal can install Podman with Chocolatey.")
            eprint("Running: choco install -y podman")
            run(["choco", "install", "-y", "podman"])
        else:
            raise RuntimeError(
                "Podman is missing and neither winget nor choco were found. Install Podman manually."
            )
    else:
        raise RuntimeError(f"Unsupported operating system: {os_name}")
    ensure_command_exists("podman")
    vprint("Podman installation completed.")


def install_self(target_dir: str = DEFAULT_INSTALL_DIR) -> None:
    script_file = globals().get("__file__")
    script_path = Path(script_file).resolve() if script_file else None
    if script_path is not None and script_path.exists() and script_path.name != "<stdin>":
        script_bytes = script_path.read_bytes()
    else:
        script_bytes = urlopen(RAW_START_PY_URL).read()
    target_parent = Path(target_dir).expanduser()
    target = target_parent / COMMAND_NAME
    if not target_parent.exists():
        try:
            target_parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as err:
            raise RuntimeError(
                f"Install directory does not exist and cannot be created without elevated privileges: {target_parent}. "
                "Create it yourself first, or choose an existing writable directory such as ~/.local/bin."
            ) from err
    if not target_parent.is_dir():
        raise RuntimeError(f"Install target is not a directory: {target_parent}")
    try:
        atomic_write(target, script_bytes, mode=0o755)
    except PermissionError:
        require_sudo_capability(
            f"Cannot write `{target}` without permission."
        )
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(script_bytes)
            tmp_src = Path(tmp.name)
        try:
            run(["sudo", "install", "-m", "755", str(tmp_src), str(target)])
        finally:
            tmp_src.unlink(missing_ok=True)
    infoprint(f"Installed launcher: {target}")
    infoprint(f"Run it from anywhere with: {target.name}")


def uninstall_self(target_dir: str = DEFAULT_INSTALL_DIR) -> None:
    target = Path(target_dir).expanduser() / COMMAND_NAME
    if not target.exists() and not target.is_symlink():
        infoprint(f"Not installed at: {target}")
        return
    if target.exists() and target.is_dir():
        raise RuntimeError(f"Refusing to remove directory: {target}")
    try:
        target.unlink()
    except PermissionError:
        require_sudo_capability(f"Cannot remove `{target}` without permission.")
        run(["sudo", "rm", "-f", str(target)])
    infoprint(f"Removed launcher: {target}")


def resolve_running_script_path() -> Path | None:
    script_file = globals().get("__file__")
    if not script_file:
        return None
    return Path(script_file).resolve()


def update_self() -> None:
    running_path = resolve_running_script_path()
    if running_path is None or running_path.name != COMMAND_NAME:
        raise RuntimeError(
            "--update only works from an installed 'podman-minimal' command, "
            "not from the repository script file."
        )
    installed_path = shutil.which(COMMAND_NAME)
    if installed_path is None or Path(installed_path).resolve() != running_path:
        raise RuntimeError(
            "--update only works when the running script is the 'podman-minimal' command found on PATH."
        )
    script_bytes = urlopen(RAW_START_PY_URL).read()
    try:
        atomic_write(running_path, script_bytes, mode=0o755)
    except PermissionError:
        require_sudo_capability(f"Cannot update `{running_path}` without permission.")
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(script_bytes)
            tmp_path = Path(tmp.name)
        try:
            run(["sudo", "install", "-m", "755", str(tmp_path), str(running_path)])
        finally:
            tmp_path.unlink(missing_ok=True)
    infoprint(f"Updated launcher in place: {running_path}")
    infoprint("Restart any running podman-minimal sessions to use the new version.")


def check_setup_prompt(script_invocation: str) -> None:
    install_target = str(Path(DEFAULT_INSTALL_DIR) / COMMAND_NAME)
    required_paths = [install_target]
    if host_os() == "linux":
        required_paths.append(SYSTEM_OCI_DIR)
    missing = [p for p in required_paths if not Path(p).exists()]
    if not missing:
        return
    vprint("Setup check: some standard host paths are missing:")
    for item in missing:
        vprint(f"  - {item}")
    vprint("Run once with automatic setup:")
    vprint(f"  {script_invocation} --install")
    vprint("")


def ensure_user_linger(user_name: str) -> None:
    if host_os() != "linux":
        raise RuntimeError("--daemon-* features require Linux (systemd user services).")
    ensure_command_exists("loginctl")
    current = run_capture(["loginctl", "show-user", user_name, "-p", "Linger", "--value"], check=False)
    if current.strip().lower() == "yes":
        return
    if os.geteuid() == 0:
        run(["loginctl", "enable-linger", user_name])
        return
    require_sudo_capability("Enabling linger for your user may require sudo.")
    vprint(f"Enabling linger for user '{user_name}' (sudo may prompt)...")
    proc = run(["sudo", "loginctl", "enable-linger", user_name], check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "Could not enable linger automatically. "
            "Run in an interactive terminal so sudo can prompt for password."
        )


def resolve_image_from_file(image_file: Path) -> str:
    if not image_file.exists():
        raise RuntimeError(f"Image file not found: {image_file}")
    output = run_capture(["podman", "load", "-i", str(image_file)])
    match = re.search(r"Loaded image:\s*(\S+)", output)
    if match:
        return match.group(1)
    raise RuntimeError(f"Could not parse loaded image name from: {output}")


def project_name_from_path(path: Path) -> str:
    cleaned = "".join(c.lower() if (c.isalnum() or c in "._-") else "-" for c in path.name)
    cleaned = cleaned.strip("-")
    cleaned = cleaned.lstrip(".")
    cleaned = cleaned.strip("-")
    return cleaned or "project"


def safe_name_component(value: str, default: str = "user") -> str:
    cleaned = "".join(c if (c.isalnum() or c in "._-") else "-" for c in value)
    cleaned = cleaned.strip("-")
    cleaned = cleaned.lstrip(".")
    return cleaned or default


def init_devcontainer(launch_dir: Path) -> None:
    devcontainers_dir = launch_dir / ".devcontainers"
    devcontainers_dir.mkdir(parents=True, exist_ok=True)

    dockerfile_path = devcontainers_dir / "Dockerfile"
    devcontainer_json_path = devcontainers_dir / "devcontainer.json"

    if not dockerfile_path.exists():
        atomic_write_text(
            dockerfile_path,
            "\n".join(
                [
                    "FROM docker.io/nvidia/cuda:12.4.1-base-ubuntu22.04",
                    "",
                    "RUN apt-get update && apt-get install -y --no-install-recommends \\",
                    "    ca-certificates \\",
                    "    curl \\",
                    "    git \\",
                    "    python3 \\",
                    "    python3-pip \\",
                    "    bash \\",
                    "    && rm -rf /var/lib/apt/lists/*",
                    "",
                    "WORKDIR /workspace",
                    "",
                    "CMD [\"bash\"]",
                    "",
                ]
            )
        )
        vprint(f"Created: {dockerfile_path}")
    else:
        vprint(f"Exists, not modified: {dockerfile_path}")

    if not devcontainer_json_path.exists():
        atomic_write_text(
            devcontainer_json_path,
            "\n".join(
                [
                    "{",
                    "  \"name\": \"podman-minimal\",",
                    "  \"build\": {",
                    "    \"dockerfile\": \"Dockerfile\",",
                    "    \"context\": \".\"",
                    "  },",
                    "  \"workspaceFolder\": \"/workspace\",",
                    "  \"workspaceMount\": \"source=${localWorkspaceFolder},target=/workspace,type=bind\",",
                    "  \"remoteUser\": \"root\"",
                    "}",
                    "",
                ]
            )
        )
        vprint(f"Created: {devcontainer_json_path}")
    else:
        vprint(f"Exists, not modified: {devcontainer_json_path}")


def find_default_dockerfile(launch_dir: Path, script_dir: Path) -> Path | None:
    candidates: List[Path] = []
    for base in (launch_dir, script_dir):
        candidates.extend(
            [
                base / "Dockerfile",
                base / ".devcontainers" / "Dockerfile",
                base / ".devcontainers" / "dockerfile",
                base / ".devcontainer" / "Dockerfile",
                base / ".devcontainer" / "dockerfile",
                base / "devcontainer" / "Dockerfile",
                base / "devcontainer" / "dockerfile",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_build_context(dockerfile: Path) -> Path:
    dockerfile = dockerfile.resolve()
    parent = dockerfile.parent
    if parent.name in (".devcontainer", ".devcontainers"):
        return parent.parent
    return parent


def detect_gpu_args() -> List[str]:
    cdi_specs = [
        Path("/etc/cdi/nvidia.yaml"),
        Path("/var/run/cdi/nvidia.yaml"),
        Path.home() / ".config/cdi/nvidia.yaml",
    ]
    for spec in cdi_specs:
        if spec.exists():
            return ["--device", "nvidia.com/gpu=all"]

    args: List[str] = []
    nvidia_nodes = [
        "/dev/nvidiactl",
        "/dev/nvidia-uvm",
        "/dev/nvidia-uvm-tools",
        "/dev/nvidia-modeset",
    ]
    for node in nvidia_nodes:
        if Path(node).exists():
            args += ["--device", node]
    for i in range(32):
        node = f"/dev/nvidia{i}"
        if Path(node).exists():
            args += ["--device", node]
    if Path("/dev/dri").exists():
        args += ["--device", "/dev/dri"]
    return args


def detect_nvidia_tool_mount_args(gpu_args: List[str]) -> List[str]:
    has_nvidia_device = any(token.startswith("/dev/nvidia") for token in gpu_args) or (
        "nvidia.com/gpu=all" in gpu_args
    )
    if not has_nvidia_device:
        return []

    mounts: List[str] = []
    if Path("/usr/bin/nvidia-smi").exists():
        mounts += ["-v", "/usr/bin/nvidia-smi:/usr/bin/nvidia-smi:ro"]
    if Path("/usr/lib/x86_64-linux-gnu").exists():
        mounts += ["-v", "/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu:ro"]
    return mounts


@dataclass
class RuntimeConfig:
    launch_dir: Path
    script_dir: Path
    image: str
    container_name: str
    port: int
    container_port: int
    dockerfile: Path | None
    force_image_rebuild: bool
    uid: int
    gid: int
    user_name: str
    user_home: Path
    verbose: bool

    @property
    def project_mount(self) -> str:
        return f"{self.launch_dir}:{self.launch_dir}:Z"


class PodmanLauncher:
    def __init__(self, cfg: RuntimeConfig) -> None:
        self.cfg = cfg
        self.gpu_args = detect_gpu_args()
        self.nvidia_tool_mount_args = detect_nvidia_tool_mount_args(self.gpu_args)

    def maybe_build(self) -> None:
        if self.cfg.dockerfile is not None:
            dockerfile = self.cfg.dockerfile
        else:
            dockerfile = find_default_dockerfile(self.cfg.launch_dir, self.cfg.script_dir)
        if dockerfile is None:
            return
        if self.cfg.image == DEFAULT_IMAGE and self.cfg.dockerfile is None:
            tag = f"local/{project_name_from_path(dockerfile.parent)}:{self.cfg.user_name}"
            self.cfg.image = tag
        context = resolve_build_context(dockerfile)
        if (
            not self.cfg.force_image_rebuild
            and run(["podman", "image", "exists", self.cfg.image], check=False).returncode == 0
        ):
            vprint(f"Skipping build (image exists: {self.cfg.image}); use --rebuild-image to rebuild")
            return
        if self.cfg.verbose:
            vprint(f"Using Dockerfile: {dockerfile}")
            vprint(f"Build context: {context}")
        vprint(f"Building image from Dockerfile: {dockerfile}")
        run(["podman", "build", "-f", str(dockerfile), "-t", self.cfg.image, str(context)])

    def ensure_image(self) -> None:
        image_exists = run(["podman", "image", "exists", self.cfg.image], check=False).returncode == 0
        if image_exists:
            vprint(f"Using local image: {self.cfg.image}")
            return
        vprint(f"Pulling image: {self.cfg.image}")
        run(["podman", "pull", self.cfg.image])

    def _common_identity_args(self) -> List[str]:
        return [
            "--user",
            f"{self.cfg.uid}:{self.cfg.gid}",
            "--userns",
            "keep-id",
        ]

    def shell_mode(self) -> None:
        args = [
            "podman",
            "run",
            "--rm",
            "-it",
            "--name",
            f"{self.cfg.container_name}-shell",
            *self._common_identity_args(),
            "-e",
            f"HOME={self.cfg.user_home}",
            "-v",
            f"{self.cfg.user_home}:{self.cfg.user_home}:Z",
            "-v",
            self.cfg.project_mount,
            *self.nvidia_tool_mount_args,
            "-w",
            str(self.cfg.launch_dir),
            *self.gpu_args,
            self.cfg.image,
            "bash",
        ]
        vprint(f"Starting interactive shell in {self.cfg.image}")
        os.execvp(args[0], args)

    def build_run_command_args(self, command: List[str]) -> List[str]:
        if not command:
            raise RuntimeError("No command provided for command mode")
        return [
            "podman",
            "run",
            "--rm",
            *self._common_identity_args(),
            "-e",
            f"HOME={self.cfg.user_home}",
            "-v",
            f"{self.cfg.user_home}:{self.cfg.user_home}:Z",
            "-v",
            self.cfg.project_mount,
            *self.nvidia_tool_mount_args,
            "-w",
            str(self.cfg.launch_dir),
            *self.gpu_args,
            self.cfg.image,
            *command,
        ]

    def run_command_mode(self, command: List[str]) -> int:
        args = self.build_run_command_args(command)
        return run(args, check=False).returncode

    def nohup_command_mode(self, command: List[str], log_file: Path) -> int:
        args = self.build_run_command_args(command)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_file.open("a", encoding="utf-8")
        if host_os() == "windows":
            creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        else:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
            )
        log_handle.flush()
        vprint(f"Nohup started (pid: {proc.pid}) log: {log_file}")

        with log_file.open("r", encoding="utf-8", errors="replace") as reader:
            reader.seek(0, os.SEEK_END)
            while proc.poll() is None:
                line = reader.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.1)
            while True:
                line = reader.readline()
                if not line:
                    break
                print(line, end="")
        return proc.returncode or 0

    def service_mode(self, command: List[str]) -> None:
        service_cmd = command or ["sleep", "infinity"]
        run(["podman", "rm", "-f", self.cfg.container_name], check=False)
        args = [
            "podman",
            "run",
            "-d",
            "--name",
            self.cfg.container_name,
            "--restart",
            "unless-stopped",
            "-p",
            f"{self.cfg.port}:{self.cfg.container_port}",
            *self._common_identity_args(),
            "-e",
            f"HOME={self.cfg.launch_dir}",
            "-v",
            self.cfg.project_mount,
            *self.nvidia_tool_mount_args,
            "-w",
            str(self.cfg.launch_dir),
            *self.gpu_args,
            self.cfg.image,
            *service_cmd,
        ]
        run(args)
        vprint(
            f"Service started: {self.cfg.container_name} "
            f"(host {self.cfg.port} -> container {self.cfg.container_port})"
        )

    def daemon_install(self, command: List[str]) -> None:
        service_cmd = command or ["sleep", "infinity"]
        unit_name = f"{self.cfg.container_name}.service"
        ensure_command_exists("systemctl")
        ensure_user_linger(self.cfg.user_name)
        run_cmd = [
            "podman",
            "run",
            "--rm",
            "--name",
            self.cfg.container_name,
            "-p",
            f"{self.cfg.port}:{self.cfg.container_port}",
            *self._common_identity_args(),
            "-e",
            f"HOME={self.cfg.launch_dir}",
            "-v",
            self.cfg.project_mount,
            *self.nvidia_tool_mount_args,
            "-w",
            str(self.cfg.launch_dir),
            *self.gpu_args,
            self.cfg.image,
            *service_cmd,
        ]
        quoted = " ".join(shlex.quote(p) for p in run_cmd)
        unit_dir = Path.home() / ".config/systemd/user"
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit_file = unit_dir / unit_name
        atomic_write_text(
            unit_file,
            "\n".join(
                [
                    "[Unit]",
                    f"Description=Podman daemon {self.cfg.container_name}",
                    "After=network-online.target",
                    "Wants=network-online.target",
                    "",
                    "[Service]",
                    f"ExecStartPre=/usr/bin/podman rm -f {self.cfg.container_name}",
                    f"ExecStart=/bin/bash -lc {shlex.quote(quoted)}",
                    f"ExecStop=/usr/bin/podman stop -t 10 {self.cfg.container_name}",
                    "Restart=always",
                    "RestartSec=3",
                    "TimeoutStartSec=180",
                    "",
                    "[Install]",
                    "WantedBy=default.target",
                    "",
                ]
            )
        )
        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", unit_name])
        vprint(
            f"Daemon installed and started: {unit_name} "
            f"(host {self.cfg.port} -> container {self.cfg.container_port})"
        )

    def daemon_remove(self) -> None:
        unit_name = f"{self.cfg.container_name}.service"
        run(["systemctl", "--user", "disable", "--now", unit_name], check=False)
        unit_file = Path.home() / ".config/systemd/user" / unit_name
        if unit_file.exists() or unit_file.is_symlink():
            if unit_file.exists() and unit_file.is_dir():
                raise RuntimeError(f"Refusing to remove directory: {unit_file}")
            unit_file.unlink()
        run(["systemctl", "--user", "daemon-reload"])
        run(["podman", "rm", "-f", self.cfg.container_name], check=False)
        vprint(f"Daemon removed: {unit_name}")

    def daemon_status(self) -> None:
        os.execvp("systemctl", ["systemctl", "--user", "status", f"{self.cfg.container_name}.service"])

    def daemon_logs(self) -> None:
        os.execvp("journalctl", ["journalctl", "--user", "-u", f"{self.cfg.container_name}.service", "-f"])


def install_root_quadlet(
    project_dir: Path,
    uid: int,
    image: str,
    container_name: str,
    host_port: int,
    container_port: int,
) -> None:
    if host_os() != "linux":
        raise RuntimeError("System Quadlet install via --install --uid/--dir requires Linux.")
    if pwd is None or grp is None:
        raise RuntimeError("Missing POSIX account modules required for Linux system setup.")
    if os.geteuid() != 0:
        raise RuntimeError("root-install mode requires sudo/root")
    pw = pwd.getpwuid(uid)
    gid = pw.pw_gid
    user_name = pw.pw_name
    group_name = grp.getgrgid(gid).gr_name
    validate_name(container_name, "container name")

    real_project = project_dir.resolve()
    if not real_project.is_dir():
        raise RuntimeError(f"Project directory does not exist: {real_project}")

    dockerfile = real_project / "Dockerfile"
    if dockerfile.exists():
        vprint(f"Building image from Dockerfile: {dockerfile}")
        run(["podman", "build", "-f", str(dockerfile), "-t", image, str(real_project)])
    else:
        run(["podman", "pull", image])

    quadlet_dir = Path("/etc/containers/systemd")
    quadlet_dir.mkdir(parents=True, exist_ok=True)
    quadlet_file = quadlet_dir / f"{container_name}.container"
    atomic_write_text(
        quadlet_file,
        "\n".join(
            [
                "[Unit]",
                f"Description=Project daemon {container_name}",
                "After=network-online.target",
                "Wants=network-online.target",
                "",
                "[Container]",
                f"ContainerName={container_name}",
                f"Image={image}",
                f"PublishPort={host_port}:{container_port}",
                f"Volume={real_project}:{real_project}:Z",
                f"WorkingDir={real_project}",
                f"User={uid}:{gid}",
                "UserNS=keep-id",
                "",
                "[Service]",
                f"User={user_name}",
                f"Group={group_name}",
                "Restart=always",
                "RestartSec=3",
                "TimeoutStartSec=180",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "",
            ]
        )
    )

    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", f"{container_name}.service"])
    vprint(f"Installed system Quadlet: {quadlet_file}")
    vprint(f"Port mapping: host {host_port} -> container {container_port}")
    vprint(f"Running as UID {uid} ({user_name})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal Podman launcher")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--update", action="store_true", help="Update installed command from main branch")
    parser.add_argument(
        "--nohup",
        nargs="?",
        const=DEFAULT_NOHUP_LOG,
        metavar="LOGFILE",
        help="Run command detached, survive terminal close, and tee output to LOGFILE",
    )
    parser.add_argument("--dockerfile", type=Path, help="Path to Dockerfile")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="Image name")
    parser.add_argument("--image-file", type=Path, help="OCI/docker archive to load via podman load")
    parser.add_argument("--name", help="Container/service name")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Host port for service/daemon")
    parser.add_argument(
        "--container-port",
        type=int,
        help="Container port (default: same as --port)",
    )
    parser.add_argument(
        "--install",
        nargs="?",
        const=DEFAULT_INSTALL_DIR,
        metavar="DIR",
        help="Install command into DIR (default: /usr/local/bin)",
    )
    parser.add_argument(
        "--uninstall",
        nargs="?",
        const=DEFAULT_INSTALL_DIR,
        metavar="DIR",
        help="Remove command from DIR (default: /usr/local/bin)",
    )
    parser.add_argument(
        "--unistall",
        dest="uninstall",
        nargs="?",
        const=DEFAULT_INSTALL_DIR,
        metavar="DIR",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--daemon-install", action="store_true", help="Install/update user daemon")
    parser.add_argument("--daemon-remove", action="store_true", help="Remove user daemon")
    parser.add_argument("--daemon-status", action="store_true", help="Show user daemon status")
    parser.add_argument("--daemon-logs", action="store_true", help="Follow user daemon logs")
    parser.add_argument(
        "--init-devcontainer",
        action="store_true",
        help="Create minimal .devcontainers/devcontainer.json and Dockerfile in current directory",
    )
    parser.add_argument("--uid", type=int, help="UID for system Quadlet install via --install")
    parser.add_argument("--dir", type=Path, help="Project directory for system Quadlet install via --install")
    parser.add_argument(
        "--rebuild-image",
        action="store_true",
        help="Run podman build even when the image tag already exists (default skips build)",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run (default: shell)")
    return parser.parse_args()


def main() -> int:
    global VERBOSE
    args = parse_args()
    VERBOSE = args.verbose
    if args.version:
        print(f"{COMMAND_NAME} {VERSION}")
        return 0

    if args.uninstall:
        uninstall_self(args.uninstall)
        return 0

    if args.update:
        update_self()
        return 0

    if args.install:
        if args.uid is not None or args.dir is not None:
            if args.uid is None or args.dir is None:
                raise RuntimeError("--install system setup requires both --uid and --dir")
            if host_os() != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
                raise RuntimeError(
                    "--install with --uid/--dir performs system Quadlet setup and must be run as root on Linux. "
                    "No files were installed."
                )
            validate_name(
                args.name or f"ubuntu-{safe_name_component(os.environ.get('USER') or getpass.getuser())}",
                "container name",
            )
        install_self(args.install)
        if args.uid is not None or args.dir is not None:
            install_root_quadlet(
                project_dir=args.dir,
                uid=args.uid,
                image=args.image,
                container_name=args.name or f"ubuntu-{safe_name_component(os.environ.get('USER') or getpass.getuser())}",
                host_port=args.port,
                container_port=args.container_port if args.container_port is not None else args.port,
            )
        return 0

    install_podman_if_missing()
    if VERBOSE:
        vprint(f"{COMMAND_NAME} {VERSION}")
        vprint(f"Update hint: run `{COMMAND_NAME} --update`")
    launch_dir = Path.cwd()
    user_name = os.environ.get("USER") or os.environ.get("USERNAME") or getpass.getuser()
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000
    user_home = Path.home()
    container_name = args.name or f"ubuntu-{safe_name_component(user_name)}"
    validate_name(container_name, "container name")
    container_port = args.container_port if args.container_port is not None else args.port
    if VERBOSE and not args.install and not args.uninstall and not args.update:
        check_setup_prompt(Path(sys.argv[0]).name)

    if args.image_file:
        args.image = resolve_image_from_file(args.image_file.resolve())

    action_flags = [
        args.daemon_install,
        args.daemon_remove,
        args.daemon_status,
        args.daemon_logs,
        args.init_devcontainer,
        bool(args.install),
        bool(args.uninstall),
        args.update,
        bool(args.nohup),
    ]
    if sum(1 for x in action_flags if x) > 1:
        raise RuntimeError("Choose only one action flag at a time")

    if args.init_devcontainer:
        init_devcontainer(launch_dir)
        return 0

    if host_os() != "linux" and (
        args.daemon_install or args.daemon_remove or args.daemon_status or args.daemon_logs
    ):
        raise RuntimeError("--daemon-* features are currently Linux-only.")

    cfg = RuntimeConfig(
        launch_dir=launch_dir,
        script_dir=Path(__file__).resolve().parent,
        image=args.image,
        container_name=container_name,
        port=args.port,
        container_port=container_port,
        dockerfile=args.dockerfile.resolve() if args.dockerfile else None,
        force_image_rebuild=args.rebuild_image,
        uid=uid,
        gid=gid,
        user_name=user_name,
        user_home=user_home,
        verbose=VERBOSE,
    )
    launcher = PodmanLauncher(cfg)
    launcher.maybe_build()
    launcher.ensure_image()
    vprint(f"Runtime image: {cfg.image}")

    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if args.nohup and not command:
        raise RuntimeError("--nohup requires a command, e.g. podman-minimal --nohup my.log -- python app.py")

    if args.daemon_install:
        launcher.daemon_install(command)
    elif args.daemon_remove:
        launcher.daemon_remove()
    elif args.daemon_status:
        launcher.daemon_status()
    elif args.daemon_logs:
        launcher.daemon_logs()
    elif args.nohup:
        return launcher.nohup_command_mode(command, Path(args.nohup).expanduser())
    elif command:
        return launcher.run_command_mode(command)
    else:
        launcher.shell_mode()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as err:
        print(f"Error: command failed ({' '.join(err.cmd)})", file=sys.stderr)
        raise SystemExit(1)
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1)
