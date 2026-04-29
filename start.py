#!/usr/bin/env python3
"""Minimal Podman launcher with optional root Quadlet installer."""

from __future__ import annotations

import argparse
import os
import pwd
import grp
import shlex
import shutil
import subprocess
import sys
import re
from urllib.request import urlopen
from dataclasses import dataclass
from pathlib import Path
from typing import List


DEFAULT_IMAGE = "docker.io/nvidia/cuda:12.4.1-base-ubuntu22.04"
DEFAULT_PORT = 18080
INSTALL_TARGET = "/usr/local/bin/podman-minimal"
SYSTEM_OCI_DIR = "/etc/containers/systemd"
RAW_START_PY_URL = "https://raw.githubusercontent.com/vincenzoml/podman-minimal/main/start.py"


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True)


def run_capture(cmd: List[str], check: bool = True) -> str:
    proc = subprocess.run(cmd, check=check, text=True, capture_output=True)
    return proc.stdout.strip()


def ensure_command_exists(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def install_self(target_path: str = INSTALL_TARGET) -> None:
    script_file = globals().get("__file__")
    script_path = Path(script_file).resolve() if script_file else None
    if script_path is not None and script_path.exists() and script_path.name != "<stdin>":
        script_bytes = script_path.read_bytes()
    else:
        script_bytes = urlopen(RAW_START_PY_URL).read()
    target = Path(target_path)
    if os.geteuid() == 0:
        target.write_bytes(script_bytes)
        os.chmod(target, 0o755)
    else:
        ensure_command_exists("sudo")
        tmp_src = Path("/tmp/podman-minimal.start.py")
        tmp_src.write_bytes(script_bytes)
        run(["sudo", "cp", str(tmp_src), str(target)])
        run(["sudo", "chmod", "755", str(target)])
        run(["rm", "-f", str(tmp_src)])
    print(f"Installed launcher: {target}")
    print(f"Run it from anywhere with: {target.name}")


def check_setup_prompt(script_invocation: str, auto_install: bool) -> None:
    missing = [p for p in (INSTALL_TARGET, SYSTEM_OCI_DIR) if not Path(p).exists()]
    if not missing:
        return
    if auto_install and sys.stdin.isatty():
        install_self()
        return
    print("Setup check: some standard host paths are missing:")
    for item in missing:
        print(f"  - {item}")
    print("Run once with automatic setup:")
    print(f"  {script_invocation} --install")
    print()


def ensure_user_linger(user_name: str) -> None:
    ensure_command_exists("loginctl")
    current = run_capture(["loginctl", "show-user", user_name, "-p", "Linger", "--value"], check=False)
    if current.strip().lower() == "yes":
        return
    if os.geteuid() == 0:
        run(["loginctl", "enable-linger", user_name])
        return
    ensure_command_exists("sudo")
    print(f"Enabling linger for user '{user_name}' (sudo may prompt)...")
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
    # podman load output example: "Loaded image: docker.io/library/ubuntu:24.04"
    match = re.search(r"Loaded image:\s*(\S+)", output)
    if match:
        return match.group(1)
    # fallback: if format differs, return full output and let caller decide.
    raise RuntimeError(f"Could not parse loaded image name from: {output}")


def project_name_from_path(path: Path) -> str:
    cleaned = "".join(c.lower() if (c.isalnum() or c in "._-") else "-" for c in path.name)
    cleaned = cleaned.strip("-")
    # OCI/docker image paths cannot use a "."-prefixed repo component (.devcontainer is common).
    cleaned = cleaned.lstrip(".")
    cleaned = cleaned.strip("-")
    return cleaned or "project"


def init_devcontainer(launch_dir: Path) -> None:
    devcontainers_dir = launch_dir / ".devcontainers"
    devcontainers_dir.mkdir(parents=True, exist_ok=True)

    dockerfile_path = devcontainers_dir / "Dockerfile"
    devcontainer_json_path = devcontainers_dir / "devcontainer.json"

    if not dockerfile_path.exists():
        dockerfile_path.write_text(
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
            ),
            encoding="utf-8",
        )
        print(f"Created: {dockerfile_path}")
    else:
        print(f"Exists, not modified: {dockerfile_path}")

    if not devcontainer_json_path.exists():
        devcontainer_json_path.write_text(
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
            ),
            encoding="utf-8",
        )
        print(f"Created: {devcontainer_json_path}")
    else:
        print(f"Exists, not modified: {devcontainer_json_path}")


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
    """Build context directory for ``podman build``.
    VS Code/Dev Containers convention: Dockerfile lives under ``.devcontainer/`` or
    ``.devcontainers/``, and ``COPY`` paths are workspace-relative — i.e. ``build.context``: ``..``
    in ``devcontainer.json``. Using only ``dockerfile.parent`` misses that and breaks COPY.
    """
    dockerfile = dockerfile.resolve()
    parent = dockerfile.parent
    if parent.name in (".devcontainer", ".devcontainers"):
        return parent.parent
    return parent


def detect_gpu_args() -> List[str]:
    # Prefer CDI (modern Podman/NVIDIA integration) when available.
    cdi_specs = [
        Path("/etc/cdi/nvidia.yaml"),
        Path("/var/run/cdi/nvidia.yaml"),
        Path.home() / ".config/cdi/nvidia.yaml",
    ]
    for spec in cdi_specs:
        if spec.exists():
            return ["--device", "nvidia.com/gpu=all"]

    # Fallback to direct device node mapping.
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
            print(f"Skipping build (image exists: {self.cfg.image}); use --rebuild-image to rebuild")
            return
        print(f"Building image from Dockerfile: {dockerfile}")
        print(f"Build context: {context}")
        run(["podman", "build", "-f", str(dockerfile), "-t", self.cfg.image, str(context)])

    def ensure_image(self) -> None:
        image_exists = run(["podman", "image", "exists", self.cfg.image], check=False).returncode == 0
        if image_exists:
            print(f"Using local image: {self.cfg.image}")
            return
        print(f"Pulling image: {self.cfg.image}")
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
        print(f"Starting interactive shell in {self.cfg.image}")
        os.execvp(args[0], args)

    def run_command_mode(self, command: List[str]) -> int:
        if not command:
            raise RuntimeError("No command provided for command mode")
        args = [
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
        return run(args, check=False).returncode

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
        print(
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
        unit_file.write_text(
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
            ),
            encoding="utf-8",
        )
        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", unit_name])
        print(
            f"Daemon installed and started: {unit_name} "
            f"(host {self.cfg.port} -> container {self.cfg.container_port})"
        )

    def daemon_remove(self) -> None:
        unit_name = f"{self.cfg.container_name}.service"
        run(["systemctl", "--user", "disable", "--now", unit_name], check=False)
        unit_file = Path.home() / ".config/systemd/user" / unit_name
        if unit_file.exists():
            unit_file.unlink()
        run(["systemctl", "--user", "daemon-reload"])
        run(["podman", "rm", "-f", self.cfg.container_name], check=False)
        print(f"Daemon removed: {unit_name}")

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
    if os.geteuid() != 0:
        raise RuntimeError("root-install mode requires sudo/root")
    pw = pwd.getpwuid(uid)
    gid = pw.pw_gid
    user_name = pw.pw_name
    group_name = grp.getgrgid(gid).gr_name

    real_project = project_dir.resolve()
    if not real_project.is_dir():
        raise RuntimeError(f"Project directory does not exist: {real_project}")

    dockerfile = real_project / "Dockerfile"
    if dockerfile.exists():
        print(f"Building image from Dockerfile: {dockerfile}")
        run(["podman", "build", "-f", str(dockerfile), "-t", image, str(real_project)])
    else:
        run(["podman", "pull", image])

    quadlet_dir = Path("/etc/containers/systemd")
    quadlet_dir.mkdir(parents=True, exist_ok=True)
    quadlet_file = quadlet_dir / f"{container_name}.container"
    quadlet_file.write_text(
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
        ),
        encoding="utf-8",
    )

    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", f"{container_name}.service"])
    print(f"Installed system Quadlet: {quadlet_file}")
    print(f"Port mapping: host {host_port} -> container {container_port}")
    print(f"Running as UID {uid} ({user_name})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal Podman launcher")
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
    parser.add_argument("--install", action="store_true", help="Run one-time setup actions")
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
    ensure_command_exists("podman")
    args = parse_args()

    launch_dir = Path.cwd()
    user_name = os.environ.get("USER") or run_capture(["id", "-un"])
    uid = os.getuid()
    gid = os.getgid()
    user_home = Path(f"/home/{user_name}")
    container_name = args.name or f"ubuntu-{user_name}"
    container_port = args.container_port if args.container_port is not None else args.port
    if not args.install:
        check_setup_prompt(Path(sys.argv[0]).name, auto_install=True)

    if args.image_file:
        args.image = resolve_image_from_file(args.image_file.resolve())

    action_flags = [
        args.daemon_install,
        args.daemon_remove,
        args.daemon_status,
        args.daemon_logs,
        args.init_devcontainer,
    ]
    if sum(1 for x in action_flags if x) > 1:
        raise RuntimeError("Choose only one action flag at a time")

    if args.install:
        install_self()
        # Unified one-time system setup path: install with UID+DIR.
        if args.uid is not None or args.dir is not None:
            if args.uid is None or args.dir is None:
                raise RuntimeError("--install system setup requires both --uid and --dir")
            install_root_quadlet(
                project_dir=args.dir,
                uid=args.uid,
                image=args.image,
                container_name=container_name,
                host_port=args.port,
                container_port=container_port,
            )
        return 0

    if args.init_devcontainer:
        init_devcontainer(launch_dir)
        return 0

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
    )
    launcher = PodmanLauncher(cfg)
    launcher.maybe_build()
    launcher.ensure_image()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if args.daemon_install:
        launcher.daemon_install(command)
    elif args.daemon_remove:
        launcher.daemon_remove()
    elif args.daemon_status:
        launcher.daemon_status()
    elif args.daemon_logs:
        launcher.daemon_logs()
    elif command:
        # Default behavior: any positional args are treated as command.
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
