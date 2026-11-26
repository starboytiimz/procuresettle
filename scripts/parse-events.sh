
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_FILE="$(mktemp)"

trap 'rm -f "$LOG_FILE"' EXIT

echo "Running ProcureSettle workspace tests..."

if cargo test --workspace --locked -- --nocapture >"$LOG_FILE" 2>&1; then
    echo
    echo "Filtering event-related test output..."
    echo

    if ! grep -Ei 'event(s)?|contract event' "$LOG_FILE"; then
        echo "No event-related console output was found."
    fi
else
    TEST_STATUS=$?

    echo "Workspace tests failed. Full output follows:" >&2
    cat "$LOG_FILE" >&2

    exit "$TEST_STATUS"
fi

echo
echo "Event inspection completed."
