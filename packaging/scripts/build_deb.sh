#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${NEXUS_VERSION:-0.1.5}"
ARCH="${NEXUS_ARCH:-amd64}"
PKG_DIR="$ROOT_DIR/dist/debroot"
OUT="$ROOT_DIR/dist/nexus_${VERSION}_${ARCH}.deb"
CARGO="${CARGO:-cargo}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

build_rust_binaries() {
  require_cmd "$CARGO"

  "$CARGO" build --manifest-path "$ROOT_DIR/nexus-iced/Cargo.toml" --release
  "$CARGO" build --manifest-path "$ROOT_DIR/watcher_rs/Cargo.toml" --release
  "$CARGO" build --manifest-path "$ROOT_DIR/core-rust/Cargo.toml" --release -p nexus_memory --bin memory_service
  "$CARGO" build --manifest-path "$ROOT_DIR/backend/Cargo.toml" --release
}

install_bin() {
  local src="$1"
  local dst="$2"
  if [[ ! -x "$src" ]]; then
    echo "Expected compiled binary not found: $src" >&2
    exit 1
  fi
  install -D -m 0755 "$src" "$dst"
}

require_cmd dpkg-deb

mkdir -p "$ROOT_DIR/dist"
rm -rf "$PKG_DIR"
mkdir -p \
  "$PKG_DIR/DEBIAN" \
  "$PKG_DIR/usr/bin" \
  "$PKG_DIR/usr/lib/nexus" \
  "$PKG_DIR/etc/nexus" \
  "$PKG_DIR/var/lib/nexus/workspace" \
  "$PKG_DIR/var/log/nexus" \
  "$PKG_DIR/lib/systemd/system" \
  "$PKG_DIR/usr/share/applications"

build_rust_binaries

cp -a "$ROOT_DIR/apps" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/bin" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/communication" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/config" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/nexus_core" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/configs" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/ui" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/models" "$PKG_DIR/usr/lib/nexus/"
cp -a "$ROOT_DIR/pattern_engine.py" "$PKG_DIR/usr/lib/nexus/pattern_engine.py"
cp -a "$ROOT_DIR/config/config.example.toml" "$PKG_DIR/etc/nexus/config.toml"
cp -a "$ROOT_DIR/config/nexus.env.example" "$PKG_DIR/etc/nexus/nexus.env"
cp -a "$ROOT_DIR/packaging/systemd/nexus.service" "$PKG_DIR/lib/systemd/system/nexus.service"
cp -a "$ROOT_DIR/packaging/desktop/nexus.desktop" "$PKG_DIR/usr/share/applications/nexus.desktop"

install_bin "$ROOT_DIR/nexus-iced/target/release/nexus-iced" "$PKG_DIR/usr/lib/nexus/bin/nexus-iced"
install_bin "$ROOT_DIR/watcher_rs/target/release/watcher_rs" "$PKG_DIR/usr/lib/nexus/bin/watcher_rs"
install_bin "$ROOT_DIR/core-rust/target/release/memory_service" "$PKG_DIR/usr/lib/nexus/bin/memory_service"
install_bin "$ROOT_DIR/backend/target/release/backend" "$PKG_DIR/usr/lib/nexus/bin/nexus-rust-backend"

find "$PKG_DIR/usr/lib/nexus" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$PKG_DIR/usr/lib/nexus" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

cat > "$PKG_DIR/usr/bin/nexus" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
cd /usr/lib/nexus
exec /usr/lib/nexus/bin/nexus "$@"
WRAPPER
chmod 0755 "$PKG_DIR/usr/bin/nexus"

cp "$ROOT_DIR/packaging/debian/control" "$PKG_DIR/DEBIAN/control"
sed -i "s/^Version: .*/Version: ${VERSION}/" "$PKG_DIR/DEBIAN/control"
cp "$ROOT_DIR/packaging/debian/conffiles" "$PKG_DIR/DEBIAN/conffiles"
cp "$ROOT_DIR/packaging/debian/postinst" "$PKG_DIR/DEBIAN/postinst"
cp "$ROOT_DIR/packaging/debian/prerm" "$PKG_DIR/DEBIAN/prerm"
cp "$ROOT_DIR/packaging/debian/postrm" "$PKG_DIR/DEBIAN/postrm"
chmod 0755 "$PKG_DIR/DEBIAN/postinst" "$PKG_DIR/DEBIAN/prerm" "$PKG_DIR/DEBIAN/postrm"

dpkg-deb --root-owner-group --build "$PKG_DIR" "$OUT"
echo "$OUT"
