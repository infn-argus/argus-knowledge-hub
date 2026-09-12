#!/bin/bash

# Builds the asset-management web app image and pushes it to GitHub Container
# Registry. Run from the webapp/ directory. Requires `docker login ghcr.io`
# beforehand.

set -e

IMAGE_NAME="ghcr.io/infn-argus/argus-knowledge-hub-web"
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
echo "Next: kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt -n assetmanagement set image deployment/assetmanagement-web web=${IMAGE_NAME}:${VERSION}"
echo "======================================"
