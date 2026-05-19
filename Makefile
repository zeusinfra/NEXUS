PYTHON ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
PIP ?= $(PYTHON) -m pip
RUFF ?= .venv/bin/ruff

.PHONY: bootstrap lint ruff-check compile test test-unit test-integration test-system rust-fmt rust-check rust-clippy rust-test rust build smoke deb install-local uninstall-local test-package clean ci

bootstrap:
	./scripts/bootstrap.sh

ruff-check:
	$(RUFF) check nexus_core apps communication tests

lint: ruff-check
	$(PYTHON) -m flake8 nexus_core apps communication tests --count --select=E9,F63,F7,F82 --show-source --statistics

compile:
	$(PYTHON) -m compileall nexus_core apps communication

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit

test-integration:
	$(PYTHON) -m pytest tests/integration

test-system:
	$(PYTHON) -m pytest tests/system

rust-fmt:
	cd core-rust && cargo fmt --all -- --check
	cd watcher_rs && cargo fmt --all -- --check
	cd backend && cargo fmt --all -- --check
	cd nexus-iced && cargo fmt --all -- --check

rust-check:
	cd core-rust && cargo check --all-targets
	cd watcher_rs && cargo check --all-targets
	cd backend && cargo check --all-targets
	cd nexus-iced && cargo check --all-targets

rust-clippy:
	cd core-rust && cargo clippy --all-targets -- -D warnings
	cd watcher_rs && cargo clippy --all-targets -- -D warnings
	cd backend && cargo clippy --all-targets -- -D warnings
	cd nexus-iced && cargo clippy --all-targets -- -D warnings

rust-test:
	cd core-rust && cargo test --all-targets
	cd watcher_rs && cargo test --all-targets
	cd backend && cargo test --all-targets
	cd nexus-iced && cargo test --all-targets

rust: rust-fmt rust-check rust-clippy rust-test

build: compile

smoke: ruff-check compile test rust-check

deb:
	bash packaging/scripts/build_deb.sh

install-local: deb
	sudo apt install ./dist/nexus_*_amd64.deb

uninstall-local:
	sudo apt remove nexus

test-package:
	test -n "$$(ls dist/nexus_*_amd64.deb 2>/dev/null)"
	dpkg-deb --info "$$(ls -1 dist/nexus_*_amd64.deb | sort -V | tail -1)"
	dpkg-deb --contents "$$(ls -1 dist/nexus_*_amd64.deb | sort -V | tail -1)" >/dev/null

clean:
	$(PYTHON) -m compileall -q nexus_core apps
	find nexus_core apps -type d -name __pycache__ -prune -exec rm -rf {} +

ci: lint test rust
