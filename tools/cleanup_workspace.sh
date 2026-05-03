#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[cleanup] Removing Python caches..."
rm -rf \
  __pycache__ \
  zeus_core/__pycache__ \
  zeus_core/v4/__pycache__ \
  cognitive-python/__pycache__ \
  communication/__pycache__ \
  scratch/__pycache__ \
  tests/__pycache__ \
  .ruff_cache || true

echo "[cleanup] Removing Rust build artifacts..."
rm -rf watcher_rs/target core-rust/target core-rust/zeus_memory/target core-rust/zeus_synapse/target || true

echo "[cleanup] Done."
