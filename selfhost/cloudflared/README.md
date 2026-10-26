# Cloudflare Tunnel (plan B)

Expose the GPU box's SGLang endpoint to the gateway **without** a relay app or
Tailscale. The GPU box runs `cloudflared`, dials out to Cloudflare, and SGLang
becomes reachable at a public hostname. LiteLLM points straight at that hostname.

```
GPU box:  SGLang :30000  +  cloudflared (dials out)
                                   │
                                   ▼
                          Cloudflare edge  https://ds.example.com
                                   ▲
LiteLLM (Fly) ─── https://ds.example.com/v1 ──┘   (api_key = SGLang key)
```

**No relay app, no Tailscale.** Traffic goes through Cloudflare (third party).

> Plan A (Tailscale + relay) is kept in `../relay/` for reference. This folder is
> the active approach.

## Trade-offs vs plan A

| | Plan B — Cloudflare Tunnel | Plan A — Tailscale relay |
|---|---|---|
| Relay app | none | required |
| Third party in path | Cloudflare (sees traffic) | none |
| Inbound ports needed | none (outbound dial) | none |
| Control plane | Cloudflare dashboard/CLI | Tailscale admin console |
| Gateway change | none (just the model entry) | none |
| Extra hardening | Cloudflare Access, WAF | private tailnet |

## Two flavors

| Flavor | Account/domain | URL | Use |
|---|---|---|---|
| **Quick tunnel** | none | random `*.trycloudflare.com` | quick test |
| **Named tunnel** | Cloudflare account + domain | your hostname (e.g. `ds.example.com`) | production |

## Local test (no GPU, no account)

See **`test-locally.md`** for exact copy-paste commands that validate the whole
chain (`LiteLLM -> quick tunnel -> stub`) end-to-end for free.

## Env

Copy `.env.example` -> `.env` and set `SGLANG_PORT`, and for named tunnels the
tunnel token or config path.

## Quick tunnel (test, no account)

On the GPU box (alongside SGLang):

```sh
MODE=quick SGLANG_PORT=30000 ./run-cloudflared.sh
# prints a https://<random>.trycloudflare.com URL; point LiteLLM api_base at it
```

Or with Docker:

```sh
docker run --rm --network host cloudflare/cloudflared:latest \
  tunnel --url http://localhost:30000
```

## Named tunnel (production)

1. **Create the tunnel** (once). Either in the Cloudflare dashboard
   (**Zero Trust -> Networks -> Tunnels -> Create**), or via CLI:

   ```sh
   cloudflared tunnel login
   cloudflared tunnel create ds-tunnel          # writes ~/.cloudflared/<id>.json
   cloudflared tunnel route dns ds-tunnel ds.example.com
   ```

2. **Configure ingress** — copy `config.example.yml` to `~/.cloudflared/config.yml`
   and set the hostname and credentials path.

3. **Run it** on the GPU box:

   ```sh
   MODE=config CF_CONFIG=$HOME/.cloudflared/config.yml ./run-cloudflared.sh
   # or token-based (token from the dashboard):
   MODE=token CF_TOKEN=<tunnel-token> ./run-cloudflared.sh
   ```

4. **Verify** the public URL reaches SGLang:

   ```sh
   curl -sS https://ds.example.com/v1/models -H "Authorization: Bearer $API_KEY"
   ```

## Upgrade path: quick -> named (later)

We start on a **quick tunnel** (random URL). Upgrading to a stable hostname is
just these steps — **no gateway or model changes**:

1. Add a **domain to Cloudflare** (free plan is fine).
2. Create the tunnel + route DNS (the "Named tunnel" steps above).
3. Run `cloudflared` in `MODE=token` or `MODE=config` instead of `MODE=quick`.
4. Update the **LiteLLM entry's `api_base`** to `https://ds.example.com/v1`
   (one field).
5. Optionally enable **Cloudflare Access** and add the `extra_headers` (below).

Why upgrade: the quick-tunnel URL **rotates on every restart**, so each restart
means editing `api_base`. A named tunnel is stable and lets you add Access/WAF.

## Then wire LiteLLM

See `litellm-integration.md` — add one model entry pointing at
`https://ds.example.com/v1` (or the quick-tunnel URL). No gateway code changes.

## Hardening (recommended for a public hostname)

- Use a **strong `API_KEY`** on SGLang (the endpoint is public).
- Optional **Cloudflare Access**: put the hostname behind a service token; then
  LiteLLM sends `CF-Access-Client-Id` / `CF-Access-Client-Secret` headers (see
  `litellm-integration.md`).
- Optional **WAF/IP allowlist**: restrict to LiteLLM's egress IPs.
- Keep `cloudflared`'s credentials file off any public repo (`.gitignore`d here).

## Cost
- Cloudflare Tunnel + DNS: **free**; a domain registration is the only cost (or
  use a quick tunnel / a domain you already own).
