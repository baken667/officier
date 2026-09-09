#!/usr/bin/env bash
set -euo pipefail

cd "$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# -gt 1 ]]; then
  echo "Usage: bash scripts/bootstrap.sh [--all]" >&2
  exit 2
fi

case "${1:-}" in
  "")
    git submodule sync -- server web-apps sdkjs
    git submodule update --init --depth 1 --jobs 3 -- server web-apps sdkjs
    ;;
  --all)
    git submodule sync --recursive
    git submodule update --init --recursive --depth 1 --jobs 4
    ;;
  *)
    echo "Usage: bash scripts/bootstrap.sh [--all]" >&2
    exit 2
    ;;
esac

python3 scripts/patches.py apply
git submodule status
