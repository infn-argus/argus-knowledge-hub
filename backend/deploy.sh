#!/bin/bash

# Builds the asset-management API image and pushes it to GitHub Container
# Registry. Run from the backend/ directory. Requires `docker login ghcr.io`
# beforehand (a GitHub PAT with `write:packages` scope as the password).

set -e

IMAGE_NAME="ghcr.io/amichelotti/assetmanagement-backend"
VERSION="${1:?Usage: ./deploy.sh <version, e.g. 0.1.0>}"

echo "======================================"
echo "Building ${IMAGE_NAME}:${VERSION}"
echo "======================================"

docker build -t "${IMAGE_NAME}:${VERSION}" -t "${IMAGE_NAME}:latest" .

echo "Pushing to ghcr.io..."
docker push "${IMAGE_NAME}:${VERSION}"
docker push "${IMAGE_NAME}:latest"

echo "======================================"
echo "Pushed ${IMAGE_NAME}:${VERSION}"
echo "Next: kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt -n assetmanagement set image deployment/assetmanagement-api api=${IMAGE_NAME}:${VERSION}"
echo "(first deploy: see ../k8s/README.md)"
echo "======================================"
