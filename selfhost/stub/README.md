# Zero-GPU stub validation

Proves the non-GPU half of the pipeline (LiteLLM -> relay -> "upstream") before
renting or owning any GPU. Takes ~5 minutes and costs nothing.

## 1. Put the stub on the tailnet (the "GPU box" role)

On a laptop/machine that will join the tailnet:

```sh
# join the same tailnet as the relay
tailscale up --hostname gpu-ds

# run the stub on the port the relay expects (default 30000)
PORT=30000 python3 selfhost/stub/stub_server.py
```

The stub now answers OpenAI-style requests at `http://gpu-ds:30000/v1`.

## 2. Point the relay at it

The relay's `UPSTREAM_HOST` defaults to `gpu-ds` (see `relay/fly.toml`), so no
change is needed if you used `--hostname gpu-ds`. Otherwise override:

```sh
fly secrets set UPSTREAM_HOST=<your-hostname> -a selfhost-relay
```

## 3. Exercise it through the relay

From any machine on the tailnet (or the relay itself):

```sh
curl -sS http://gpu-ds:30000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"stub-model","messages":[{"role":"user","content":"ping"}]}'
# expect: "STUB: routing OK"
```

Confirm LiteLLM reaches the relay over 6PN (from the gateway app):

```sh
curl -sS http://selfhost-relay.internal:8080/v1/models
```

## 4. Add a temporary LiteLLM entry and fire a real request

See `selfhost/litellm-integration.md`. Use `model_name: selfhost-stub` and
`api_base: http://selfhost-relay.internal:8080/v1`, then:

```sh
curl -sS https://<gateway-host>/v1/chat/completions \
  -H "Authorization: Bearer <virtual-key>" \
  -H 'Content-Type: application/json' \
  -d '{"model":"selfhost-stub","messages":[{"role":"user","content":"ping"}]}'
```

Check the LiteLLM **Logs / Spend** view for the request row. Then delete the
temporary `selfhost-stub` entry.

If this passes, the only untested piece left is `serve.sh` on real GPUs.
