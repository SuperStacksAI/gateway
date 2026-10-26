#!/bin/sh
set -e

# Joins the tailnet in userspace-networking mode (Fly machines can't use TUN),
# exposing a local HTTP proxy that Caddy routes upstream connections through.

: "${TS_AUTHKEY:?set TS_AUTHKEY (Tailscale auth key)}"
TS_HOSTNAME="${TS_HOSTNAME:-selfhost-relay}"
PROXY_ADDR="localhost:1055"

mkdir -p /var/lib/tailscale /var/run/tailscale /var/log

tailscaled \
  --tun=userspace-networking \
  --socks5-server="${PROXY_ADDR}" \
  --outbound-http-proxy-listen="${PROXY_ADDR}" \
  --state=/var/lib/tailscale/tailscaled.state \
  >/var/log/tailscaled.log 2>&1 &

# Wait for the tailscaled control socket.
i=0
while [ ! -S /var/run/tailscale/tailscaled.sock ]; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "tailscaled did not start in time" >&2
    cat /var/log/tailscaled.log >&2 || true
    exit 1
  fi
  sleep 0.5
done

tailscale up --authkey="${TS_AUTHKEY}" --hostname="${TS_HOSTNAME}" --ephemeral ${TS_EXTRA_ARGS:-}

echo "relay up as ${TS_HOSTNAME}; upstream ${UPSTREAM_HOST:-gpu-ds}:${UPSTREAM_PORT:-30000}"

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
