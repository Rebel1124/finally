#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_NAME="finally-app"
CONTAINER_NAME="finally-app"

BUILD=false
RESET=false
for arg in "$@"; do
  case "$arg" in
    --build) BUILD=true ;;
    --reset) RESET=true ;;
  esac
done

if [[ "$BUILD" == true ]] || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building Docker image..."
  docker build -t "$IMAGE_NAME" .
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "Removing existing container..."
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

mkdir -p db

if [[ "$RESET" == true ]]; then
  echo "Resetting portfolio data (--reset): removing db/finally.db..."
  rm -f db/finally.db db/finally.db-journal
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  -v "$(pwd)/db:/app/db" \
  -p 8000:8000 \
  --env-file .env \
  "$IMAGE_NAME"

echo "FinAlly is running at http://localhost:8000"
