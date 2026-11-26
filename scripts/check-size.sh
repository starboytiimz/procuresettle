
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WASM_FILE="target/wasm32v1-none/release/procuresettle.wasm"
MAX_SIZE=45000

echo "======================================"
echo " ProcureSettle WASM Size Checker"
echo "======================================"

if [ ! -f "$WASM_FILE" ]; then
    echo "Error: Compiled WASM file not found."
    echo "Expected location: $WASM_FILE"
    echo "Run ./scripts/build-release.sh first."
    exit 1
fi

WASM_SIZE=$(wc -c < "$WASM_FILE" | tr -d '[:space:]')
WASM_KB=$(awk -v size="$WASM_SIZE" 'BEGIN {
    printf "%.2f", size / 1024
}')

echo ""
echo "WASM Artifact: $WASM_FILE"
echo "File Size: ${WASM_SIZE} bytes"
echo "File Size: ${WASM_KB} KB"
echo "Maximum Threshold: ${MAX_SIZE} bytes"

echo ""

if [ "$WASM_SIZE" -gt "$MAX_SIZE" ]; then
    echo "WARNING: WASM binary exceeds the 45KB size threshold!"
    echo "Consider optimizing the contract to reduce its size."
else
    echo "SUCCESS: WASM binary is within the size threshold."
fi
