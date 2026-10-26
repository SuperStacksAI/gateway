#!/usr/bin/env bash
set -euo pipefail

# Runs cloudflared on the GPU box to expose the local SGLang endpoint.
#
#   MODE=quick  SGLANG_PORT=30000              ./run-cloudflared.sh   # test, no account
#   MODE=token  CF_TOKEN=<token>               ./run-cloudflared.sh   # named, dashboard token
#   MODE=config CF_CONFIG=~/.cloudflared/config.yml ./run-cloudflared.sh  # named, local config

MODE="${MODE:-quick}"
SGLANG_PORT="${SGLANG_PORT:-30000}"
CF_TOKEN="${CF_TOKEN:-}"
CF_CONFIG="${CF_CONFIG:-$HOME/.cloudflared/config.yml}"

command -v cloudflared >/dev/null 2>&1 || {
  echo "cloudflared not found. Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  exit 1
}

case "$MODE" in
  quick)
    exec cloudflared tunnel --url "http://localhost:${SGLANG_PORT}"
    ;;
  token)
    [ -n "$CF_TOKEN" ] || { echo "MODE=token requires CF_TOKEN" >&2; exit 1; }
    exec cloudflared tunnel run --token "$CF_TOKEN"
    ;;
  config)
    [ -f "$CF_CONFIG" ] || { echo "config not found: $CF_CONFIG" >&2; exit 1; }
    exec cloudflared tunnel --config "$CF_CONFIG" run
    ;;
  *)
    echo "MODE must be one of: quick | token | config" >&2
    exit 1
    ;;
esac
