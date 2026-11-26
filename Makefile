
.PHONY: build test fmt lint check check-evidence clean

# Build the ProcureSettle Soroban contract.
build:
	stellar contract build --locked --package procuresettle

# Run all Rust workspace tests.
test:
	cargo test --workspace --locked

# Verify Rust formatting without modifying files.
fmt:
	cargo fmt --all -- --check

# Run strict Clippy checks across all workspace targets.
lint:
	cargo clippy --workspace --all-targets --locked -- -D warnings

# Run the standard development checks.
check: fmt lint test check-evidence

# Verify evidence bundle checksums.
check-evidence:
	python3 scripts/verify-evidence-checksums.py

# Remove generated Cargo build artifacts.
clean:
	cargo clean
