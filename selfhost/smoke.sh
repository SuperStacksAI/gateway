#!/usr/bin/env bash
set -euo pipefail

# Smoke test: hit the OpenAI-compatible /v1/chat/completions endpoint.

BASE="${BASE:-http://localhost:30000}"
API_KEY="${API_KEY:?set API_KEY}"
MODEL="${MODEL:-deepseek-ai/DeepSeek-V4.1-Flash}"

curl -sS "$BASE/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: READY\"}],\"max_tokens\":32}"
echo
