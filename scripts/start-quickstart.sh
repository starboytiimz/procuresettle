#!/usr/bin/env bash
#
# start-quickstart.sh — Launch and wait for a local Stellar Quickstart container.
#
# Usage:
#   ./scripts/start-quickstart.sh [OPTIONS]
#
# Options:
#   --stop    Stop and remove the running Quickstart container.
#   --help    Show this help message.
#
# Environment variables (optional):
#   QUICKSTART_CONTAINER  Container name (default: stellar-procuresettle-local)
#   QUICKSTART_IMAGE_DIGEST  Pinned image digest (default: from CI)
#   QUICKSTART_IMAGE_TAG     Image tag derived from digest (default: auto-generated)
#
# The default image digest matches the pinned version used in .github/workflows/ci.yml.
# To use a different Quickstart version, override QUICKSTART_IMAGE_DIGEST.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

QUICKSTART_CONTAINER="${QUICKSTART_CONTAINER:-stellar-procuresettle-local}"
QUICKSTART_IMAGE_DIGEST="${QUICKSTART_IMAGE_DIGEST:-sha256:4f8dfd693deba57fddef7f0bc722e4782c2e606c8675e3adc5438cebae249295}"
# Derive a short tag from the digest for readability.
QUICKSTART_IMAGE_TAG="procuresettle-${QUICKSTART_IMAGE_DIGEST:7:12}"

STDIN_SINK=/dev/null

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

show_help() {
    sed -n '^# Usage:' "$0" | sed 's/^# //; s/^#//'
    exit 0
}

# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

do_stop() {
    if docker container inspect "$QUICKSTART_CONTAINER" >/dev/null 2>&1; then
        echo "Stopping Quickstart container: $QUICKSTART_CONTAINER"
        docker container stop "$QUICKSTART_CONTAINER"
        docker container rm "$QUICKSTART_CONTAINER"
        echo "Stopped and removed container."
    else
        echo "No running container named '$QUICKSTART_CONTAINER' found."
    fi
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

if [ "${1:-}" = "--stop" ]; then
    do_stop
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
fi

# ---------------------------------------------------------------------------
# Check Docker
# ---------------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed or not in PATH." >&2
    echo "Please install Docker and try again." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running or you lack permissions." >&2
    echo "Please start Docker and ensure your user can access it." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Pull and tag the pinned image
# ---------------------------------------------------------------------------

echo "Pulling Quickstart image: stellar/quickstart@$QUICKSTART_IMAGE_DIGEST"
docker pull "stellar/quickstart@$QUICKSTART_IMAGE_DIGEST"

echo "Tagging image: stellar/quickstart:$QUICKSTART_IMAGE_TAG"
docker tag "stellar/quickstart@$QUICKSTART_IMAGE_DIGEST" "stellar/quickstart:$QUICKSTART_IMAGE_TAG"

# Verify the tag points to the expected digest.
digest_image_id=$(docker image inspect "stellar/quickstart@$QUICKSTART_IMAGE_DIGEST" --format '{{.Id}}')
tagged_image_id=$(docker image inspect "stellar/quickstart:$QUICKSTART_IMAGE_TAG" --format '{{.Id}}')
if [ "$digest_image_id" != "$tagged_image_id" ]; then
    echo "Error: Image tag does not match expected digest." >&2
    exit 1
fi
echo "Pinned Quickstart image: stellar/quickstart@$QUICKSTART_IMAGE_DIGEST (image_id=$digest_image_id)"

# ---------------------------------------------------------------------------
# Start container
# ---------------------------------------------------------------------------

if docker container inspect "$QUICKSTART_CONTAINER" >/dev/null 2>&1; then
    echo "Container '$QUICKSTART_CONTAINER' already exists. Removing..."
    docker container rm -f "$QUICKSTART_CONTAINER" >/dev/null 2>&1 || true
fi

echo "Starting Quickstart container: $QUICKSTART_CONTAINER"
docker run -d \
    --name "$QUICKSTART_CONTAINER" \
    --cpus 2 \
    --memory 4g \
    -p 8000:8000 \
    -p 8001:8001 \
    -p 8002:8002 \
    stellar/quickstart:"$QUICKSTART_IMAGE_TAG" \
    --binary-url https://github.com/stellar/stellar-core/releases/download/recent-core-artifacts/stellar-core-18.0.0-x86_64-pc-linux-gnu.tar.gz

# ---------------------------------------------------------------------------
# Wait for Horizon readiness
# ---------------------------------------------------------------------------

echo "Waiting for Quickstart Horizon to become ready..."
ready=false
max_attempts=60
for attempt in $(seq 1 $max_attempts); do
    if curl --silent --show-error --fail http://localhost:8000/health \
        --output /tmp/quickstart-health.json 2>/dev/null \
        && jq -e '.database_connected == true and .core_up == true and .core_synced == true' \
            /tmp/quickstart-health.json >/dev/null 2>&1 \
        && curl --silent --show-error --fail http://localhost:8000/ \
            --output /tmp/quickstart-horizon-root.json 2>/dev/null; then
        ready=true
        break
    fi
    if [ "$attempt" -le "$max_attempts" ]; then
        sleep 5
    fi
done

if [ "$ready" != true ]; then
    echo "Error: Quickstart Horizon did not become ready after $max_attempts attempts." >&2
    echo "Health check output:" >&2
    cat /tmp/quickstart-health.json 2>/dev/null || true
    exit 1
fi

echo "Quickstart Horizon is ready!"
echo ""
echo "Local Stellar network is running:"
echo "  - Horizon: http://localhost:8000"
echo "  - Friendbot: http://localhost:8000/friendbot"
echo "  - Container: $QUICKSTART_CONTAINER"
echo "  - Image: stellar/quickstart:$QUICKSTART_IMAGE_TAG"
echo ""
echo "To stop the container, run: $0 --stop"
