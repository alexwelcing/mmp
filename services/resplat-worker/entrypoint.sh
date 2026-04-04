#!/usr/bin/env bash
set -euo pipefail

echo "ReSplat Worker starting..."
echo "Pretrained dir: /app/resplat/pretrained"
echo "Output dir: /app/resplat/outputs"

# Verify pretrained weights are available (optional sanity check).
if [ ! -d "/app/resplat/pretrained" ]; then
    echo "WARNING: /app/resplat/pretrained is missing. Inference will fail until weights are mounted."
fi

# Start the HTTP inference service.
exec python /app/resplat/infer.py "$@"
