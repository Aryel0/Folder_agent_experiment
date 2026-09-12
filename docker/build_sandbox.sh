#!/usr/bin/env bash
set -e

TAG="${1:-agent-sandbox:latest}"
echo "Building Docker sandbox image: ${TAG}..."
docker build -t "${TAG}" -f docker/Dockerfile.sandbox .
echo "Docker sandbox image built successfully!"
