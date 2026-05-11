PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: bootstrap lint test test-unit test-integration test-system rust-fmt rust-clippy rust-test rust ci

bootstrap:
	./scripts/bootstrap.sh

lint:
	$(PYTHON) -m ruff check zeus_core apps communication tests
	$(PYTHON) -m flake8 zeus_core apps communication tests --count --select=E9,F63,F7,F82 --show-source --statistics

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

ci: lint test rust
