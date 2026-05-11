#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[cleanup] Removing Python caches..."
rm -rf \
  __pycache__ \
  nexus_core/__pycache__ \
  nexus_core/v4/__pycache__ \
  cognitive-python/__pycache__ \
  communication/__pycache__ \
  scratch/__pycache__ \
  tests/__pycache__ \
  .ruff_cache || true

echo "[cleanup] Removing Rust build artifacts..."
rm -rf watcher_rs/target core-rust/target core-rust/nexus_memory/target core-rust/nexus_synapse/target || true

echo "[cleanup] Done."
