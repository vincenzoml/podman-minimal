#!/usr/bin/env bash
set -euo pipefail

VERSION="0.7.0"
REPO_URL="https://github.com/vincenzoml/podman-minimal"

echo "podman-minimal ${VERSION} - Minimal Podman launcher with GPU autodetection"
echo "Repository: ${REPO_URL}"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/start.py" "$@"
