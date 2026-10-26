#!/usr/bin/env bash
set -euo pipefail

# Pre-download model weights to a local cache/volume so serving does not need to
# pull hundreds of GB at boot.
#
# Requires the HF CLI:  pip install -U "huggingface_hub[cli]"

# V4.1-Flash is ~510GB. On RunPod, set DEST to the network volume, e.g.
#   DEST=/workspace/hf ./download-weights.sh
MODEL_ID="${MODEL_ID:-deepseek-ai/DeepSeek-V4.1-Flash-1017}"
DEST="${DEST:-$HOME/.cache/huggingface/models}"
TARGET="$DEST/$(echo "$MODEL_ID" | tr '/' '_')"

mkdir -p "$TARGET"

echo "Downloading $MODEL_ID -> $TARGET"
hf download "$MODEL_ID" --local-dir "$TARGET"
echo "Done: $TARGET"
