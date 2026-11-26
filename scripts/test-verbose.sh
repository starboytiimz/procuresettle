
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export RUST_BACKTRACE=1

echo "======================================"
echo " ProcureSettle Verbose Test Runner"
echo "======================================"

echo "Running Cargo tests with backtrace and full output..."

exec cargo test --color always -- --nocapture
