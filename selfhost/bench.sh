#!/usr/bin/env bash
set -euo pipefail

# Throughput/latency benchmark using SGLang's built-in bench_serving.
# Requires sglang installed (run inside the sglang image, or on a box with sglang).

BASE="${BASE:-http://localhost:30000}"
MODEL="${MODEL:-deepseek-ai/DeepSeek-V4.1-Flash}"
NUM_PROMPTS="${NUM_PROMPTS:-256}"
INPUT_LEN="${INPUT_LEN:-1024}"
OUTPUT_LEN="${OUTPUT_LEN:-256}"

python3 -m sglang.bench_serving \
  --backend sglang \
  --base-url "$BASE" \
  --model "$MODEL" \
  --num-prompts "$NUM_PROMPTS" \
  --random-input-len "$INPUT_LEN" \
  --random-output-len "$OUTPUT_LEN"
