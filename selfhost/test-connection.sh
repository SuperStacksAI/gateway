#!/usr/bin/env bash
set -uo pipefail

# Walks the whole chain and reports each hop, so you can see exactly where a
# connection breaks:  GPU(SGLang) -> relay -> gateway(LiteLLM) -> response.
#
# Configure via env (all optional; defaults shown):
#   LOCAL_BASE=http://localhost:30000          # SGLang on the GPU box (run on that box)
#   RELAY_BASE=http://selfhost-relay.internal:8080   # relay (run from a Fly app)
#   GATEWAY_BASE=https://<gateway-host>        # public LiteLLM endpoint
#   MODEL=<served model name>                  # e.g. qwen-tiny / deepseek-v4.1
#   API_KEY=<upstream SGLang key>              # for hops 1-2
#   VIRTUAL_KEY=<LiteLLM virtual key>          # for hop 3
#
# Only checks the hops whose base URL you provide.

LOCAL_BASE="${LOCAL_BASE:-http://localhost:30000}"
RELAY_BASE="${RELAY_BASE:-}"
GATEWAY_BASE="${GATEWAY_BASE:-}"
MODEL="${MODEL:-}"
API_KEY="${API_KEY:-}"
VIRTUAL_KEY="${VIRTUAL_KEY:-}"

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
skip() { printf '  \033[33mSKIP\033[0m %s\n' "$1"; }

chat() { # $1=base $2=bearer $3=model
  curl -sS --max-time 30 "$1/v1/chat/completions" \
    -H "Authorization: Bearer $2" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$3\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":16}"
}

models() { # $1=base $2=bearer(optional)
  if [ -n "${2:-}" ]; then
    curl -sS --max-time 15 "$1/v1/models" -H "Authorization: Bearer $2"
  else
    curl -sS --max-time 15 "$1/v1/models"
  fi
}

echo "== Chain test =="

echo "[1/3] GPU box (SGLang)  ${LOCAL_BASE}"
if models "$LOCAL_BASE" "$API_KEY" >/dev/null 2>&1; then
  pass "reachable"
  if [ -n "$MODEL" ]; then
    out="$(chat "$LOCAL_BASE" "$API_KEY" "$MODEL")"
    if printf '%s' "$out" | grep -q '"choices"'; then pass "chat ok ($MODEL)"; else fail "chat: $out"; fi
  else
    skip "set MODEL to test a completion"
  fi
else
  fail "not reachable (is SGLang up / right base?)"
fi

echo "[2/3] Relay  ${RELAY_BASE:-<unset>}"
if [ -z "$RELAY_BASE" ]; then
  skip "set RELAY_BASE (run this from the GPU box tailnet or a Fly app)"
elif models "$RELAY_BASE" "$API_KEY" >/dev/null 2>&1; then
  pass "reachable"
  if [ -n "$MODEL" ]; then
    out="$(chat "$RELAY_BASE" "$API_KEY" "$MODEL")"
    if printf '%s' "$out" | grep -q '"choices"'; then pass "chat ok (proxied)"; else fail "chat: $out"; fi
  fi
else
  fail "not reachable (relay down, wrong UPSTREAM_HOST, or not on the path?)"
fi

echo "[3/3] Gateway (LiteLLM)  ${GATEWAY_BASE:-<unset>}"
if [ -z "$GATEWAY_BASE" ]; then
  skip "set GATEWAY_BASE + VIRTUAL_KEY to test the public endpoint"
elif [ -z "$VIRTUAL_KEY" ]; then
  skip "set VIRTUAL_KEY"
elif [ -z "$MODEL" ]; then
  skip "set MODEL to the LiteLLM model_name"
else
  out="$(chat "$GATEWAY_BASE" "$VIRTUAL_KEY" "$MODEL")"
  if printf '%s' "$out" | grep -q '"choices"'; then
    pass "end-to-end ok"
  else
    fail "gateway: $out"
  fi
fi

echo "== done (check LiteLLM Logs/Spend for the request row) =="
