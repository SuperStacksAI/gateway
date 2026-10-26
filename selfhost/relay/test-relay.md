# Testing the relay app

The relay (`selfhost-relay`) is a private bridge: it joins the Tailscale tailnet
(userspace mode) and reverse-proxies LiteLLM's requests to the GPU box. Test it in
5 levels, cheapest first.

Prereqs: a **Tailscale auth key**, and an upstream to proxy to (the stub, LM
Studio, or the GPU box running SGLang).

## Level 1 — static checks (no deploy, no GPU)

```sh
docker build -t selfhost-relay selfhost/relay
docker run --rm --entrypoint caddy selfhost-relay \
  validate --config /etc/caddy/Caddyfile --adapter caddyfile
fly config validate -c selfhost/relay/fly.toml
```

Success: all exit 0.

## Level 2 — run it locally in Docker (best value; no Fly, no GPU)

Tailscale userspace mode works inside a container on macOS, so you can fully test
the relay locally.

```sh
# upstream: join the Mac to the tailnet and run the stub
tailscale up --hostname gpu-ds
PORT=30000 python3 selfhost/stub/stub_server.py &

# relay: point it at the stub
docker run --rm -p 8080:8080 \
  -e TS_AUTHKEY=<tailscale-auth-key> \
  -e UPSTREAM_HOST=gpu-ds -e UPSTREAM_PORT=30000 \
  selfhost-relay

# hit the relay — expect "STUB: routing OK"
curl -sS http://localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"stub-model","messages":[{"role":"user","content":"ping"}]}'
```

Success: logs show `relay up as selfhost-relay` and the curl returns the stub reply.

## Level 3 — deploy to Fly and confirm it's up

```sh
fly apps create selfhost-relay
fly secrets set TS_AUTHKEY=<tailscale-auth-key> -a selfhost-relay
fly deploy -c selfhost/relay/fly.toml
fly logs -a selfhost-relay            # expect: "relay up as selfhost-relay"
fly ssh console -a selfhost-relay     # then:
#   tailscale status                  # should list gpu-ds
#   wget -qO- http://localhost:8080/v1/models
```

## Level 4 — reachability from the gateway over Fly 6PN

```sh
fly ssh console -a superstackai-gateway
# inside the gateway machine:
curl -sS http://selfhost-relay.internal:8080/v1/models
```

Success: returns the upstream's `/v1/models` over the private network.

## Level 5 — full end-to-end

Add the temporary LiteLLM entry (see `../litellm-integration.md`) and call the
gateway with a **virtual key**; confirm a **spend row** appears. Use
`../test-connection.sh` to walk all hops at once.

## What each level catches

| Level | Catches |
|---|---|
| 1 | Dockerfile / config syntax |
| 2 | Tailscale join + Caddy forwarding (free) |
| 3 | Fly deploy, secrets, boot |
| 4 | Fly 6PN reachability |
| 5 | Auth, routing, billing through the gateway |

## Common failures

- Expired or already-used (non-reusable) Tailscale auth key.
- `UPSTREAM_HOST` not matching the tailnet hostname.
- Upstream not listening on `0.0.0.0` (so the relay can't reach it).
- GPU box not joined to the tailnet.
- Caddy proxy address mismatch (should be `localhost:1055`, the userspace proxy).
