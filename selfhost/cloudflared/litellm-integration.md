# Wiring the Cloudflare-tunneled model into LiteLLM (plan B)

No relay app. The gateway talks to the GPU box through its Cloudflare hostname.
The gateway app is **untouched** — only a model entry is added/repointed.

## 1. Store the upstream key as a Fly secret

The SGLang `API_KEY` (from `../.env`) becomes the upstream key:

```sh
fly secrets set SELFHOST_DS_KEY=<the SGLang API_KEY> -a superstackai-gateway
```

## 2. Add the model entry (UI or API)

```json
{
  "model_name": "deepseek-v4.1",
  "litellm_params": {
    "model": "openai/deepseek-ai/DeepSeek-V4.1-Flash",
    "api_base": "https://ds.example.com/v1",
    "api_key": "os.environ/SELFHOST_DS_KEY"
  },
  "model_info": {
    "input_cost_per_token": 0.0,
    "output_cost_per_token": 0.0
  }
}
```

Replace `ds.example.com` with your tunnel hostname (or the quick-tunnel URL for a
test). Set `input/output_cost_per_token` to your internal price so credits/spend
still compute.

## 3. If using Cloudflare Access (optional)

Add the service-token headers so LiteLLM can pass the Access gate:

```json
"extra_headers": {
  "CF-Access-Client-Id": "os.environ/CF_ACCESS_CLIENT_ID",
  "CF-Access-Client-Secret": "os.environ/CF_ACCESS_CLIENT_SECRET"
}
```

and set the secrets:

```sh
fly secrets set \
  CF_ACCESS_CLIENT_ID=<id> \
  CF_ACCESS_CLIENT_SECRET=<secret> \
  -a superstackai-gateway
```

(If your LiteLLM build doesn't expand `os.environ/` inside `extra_headers`, paste
the literal values instead.)

## 4. Verify

```sh
curl -sS https://<gateway-host>/v1/chat/completions \
  -H "Authorization: Bearer <virtual-key>" \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4.1","messages":[{"role":"user","content":"hi"}]}'
```

Virtual keys are `["*"]`, so every existing user can call `deepseek-v4.1`
immediately — no key or app changes.

## 5. Switching models later

Update `../.env`'s `MODEL_ID` (restart `serve.sh`); the Cloudflare hostname and the
LiteLLM entry stay the same when the served name is unchanged. The user-facing
`model_name` can remain `deepseek-v4.1`.

## Notes

- Unlike plan A, there is **no `selfhost-relay` app** and **no Tailscale** — the
  GPU box's `cloudflared` connects out to Cloudflare.
- The endpoint is **public**; rely on the SGLang `API_KEY` and (recommended)
  Cloudflare Access / WAF.
- UI login is the **master key** (`LITELLM_MASTER_KEY` Fly secret).
