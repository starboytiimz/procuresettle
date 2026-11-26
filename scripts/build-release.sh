
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WASM_FILE="target/wasm32v1-none/release/procuresettle.wasm"

echo "======================================"
echo " ProcureSettle Release WASM Build"
echo "======================================"

if ! command -v stellar >/dev/null 2>&1; then
    echo "Error: Stellar CLI is not installed or not in PATH." >&2
    exit 1
fi

echo "Building optimized release contract..."

if ! stellar contract build --locked --package procuresettle; then
    echo "Error: Contract release build failed." >&2
    exit 1
fi

if [ ! -s "$WASM_FILE" ]; then
    echo "Error: Expected WASM artifact was not generated:"
    echo "$WASM_FILE"
    exit 1
fi

echo ""
echo "Release build completed successfully."
echo "Compiled WASM: $ROOT_DIR/$WASM_FILE"

WASM_SIZE=$(wc -c < "$WASM_FILE" | tr -d '[:space:]')

echo "WASM Size: ${WASM_SIZE} bytes"
