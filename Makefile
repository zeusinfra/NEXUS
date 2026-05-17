PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: bootstrap lint test test-unit test-integration test-system rust-fmt rust-clippy rust-test rust build deb install-local uninstall-local test-package clean ci

bootstrap:
	./scripts/bootstrap.sh

lint:
	$(PYTHON) -m ruff check nexus_core apps communication tests
	$(PYTHON) -m flake8 nexus_core apps communication tests --count --select=E9,F63,F7,F82 --show-source --statistics

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

rust-clippy:
	cd core-rust && cargo clippy --all-targets -- -D warnings
	cd watcher_rs && cargo clippy --all-targets -- -D warnings

rust-test:
	cd core-rust && cargo test --all-targets
	cd watcher_rs && cargo test --all-targets

rust: rust-fmt rust-clippy rust-test

build:
	$(PYTHON) -m compileall nexus_core apps

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
