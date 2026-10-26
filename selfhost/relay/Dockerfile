# Private relay: joins the Tailscale tailnet (userspace mode, since Fly machines
# have no TUN) and reverse-proxies LiteLLM's requests to the GPU box running
# SGLang. No public IP; reachable by the gateway over Fly 6PN (*.internal).
FROM caddy:2-alpine

RUN apk add --no-cache tailscale \
  && mkdir -p /var/lib/tailscale /var/run/tailscale /var/log

COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
