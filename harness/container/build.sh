#!/usr/bin/env bash
# Build the SecDevQA per-item evaluation image (rootless podman).
#
#   harness/container/build.sh            # build localhost/secdevqa-eval:<version>
#   IMAGE_TAG=dev harness/container/build.sh
#
# The harness source is bind-mounted at run time, so the build context is only this directory
# (fast, cache-friendly). Bump the pinned agent versions via --build-arg when needed.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image="localhost/secdevqa-eval"
tag="${IMAGE_TAG:-$(date +%Y%m%d)}"

echo "Building ${image}:${tag} from ${here}/Containerfile ..."
podman build \
    -t "${image}:${tag}" \
    -t "${image}:latest" \
    -f "${here}/Containerfile" \
    "${here}"

echo "Done: ${image}:${tag}"
podman image inspect "${image}:${tag}" --format 'size: {{.Size}}'
