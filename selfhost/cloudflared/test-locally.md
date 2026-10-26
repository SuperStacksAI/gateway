# Local plan-B test (no GPU, no Cloudflare account)

Validates the whole plan-B chain end-to-end for free:
`LiteLLM -> Cloudflare quick tunnel -> stub` (stub stands in for SGLang).

Chain tested:

```
virtual key -> gateway (LiteLLM, on Fly) -> https://<random>.trycloudflare.com
            -> cloudflared (your Mac) -> stub :30000  -> response + spend row
```

## 0. Set variables

```sh
export GATEWAY="https://<your-gateway-host>"     # e.g. https://superstackai-gateway.fly.dev
export MASTER_KEY="sk-ff..."
export STUB_PORT=30000
export STUB_MODEL="stub-model"
```

## 1. Install cloudflared

```sh
brew install cloudflared
cloudflared --version
```

## 2. Start the upstream (stub) in a terminal

```sh
# run from selfhost/cloudflared/ (this doc's dir)
PORT=$STUB_PORT python3 ../stub/stub_server.py
# or from repo root:  PORT=30000 python3 selfhost/stub/stub_server.py

# sanity check (new terminal):
curl -sS http://localhost:$STUB_PORT/v1/models
```

## 3. Open a quick tunnel in another terminal

```sh
MODE=quick SGLANG_PORT=$STUB_PORT ./run-cloudflared.sh
# copy the printed URL, e.g. https://random-words-1234.trycloudflare.com
export TUNNEL="https://random-words-1234.trycloudflare.com"
```

Verify the tunnel reaches the stub:

```sh
curl -sS "$TUNNEL/v1/models"
```

## 4. Add a temporary LiteLLM model entry

```sh
curl -sS "$GATEWAY/model/new" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model_name\": \"selfhost-test\",
    \"litellm_params\": {
      \"model\": \"openai/$STUB_MODEL\",
      \"api_base\": \"$TUNNEL/v1\",
      \"api_key\": \"dummy\"
    },
    \"model_info\": { \"input_cost_per_token\": 0.0, \"output_cost_per_token\": 0.0 }
  }"
# note the returned "model_info.id" -> export MODEL_ID=...
```

## 5. Create a virtual key and call the gateway

```sh
export VK=$(curl -sS "$GATEWAY/key/generate" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["key"])')

curl -sS "$GATEWAY/v1/chat/completions" \
  -H "Authorization: Bearer $VK" \
  -H "Content-Type: application/json" \
  -d '{"model":"selfhost-test","messages":[{"role":"user","content":"ping"}]}'
# expect: "STUB: routing OK"
```

Then check the LiteLLM **Logs / Spend** view for the request row.

## 6. Clean up

```sh
# remove the temporary model entry
curl -sS "$GATEWAY/model/delete" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"id\": \"$MODEL_ID\"}"

# stop the stub and the tunnel (Ctrl-C in their terminals)
```

## Expected result

- `/v1/chat/completions` returns `STUB: routing OK` **through the gateway**.
- A spend/usage row appears for the virtual key.
- If these pass, plan B is proven; only `serve.sh` on real GPUs remains untested.

## Common failures

- Tunnel URL expired/rotated -> re-copy from the cloudflared output.
- `api_base` must include `/v1`.
- Model `id` mismatch on delete -> use the value returned by `/model/new`.
- Stub not listening on `0.0.0.0` (default is `0.0.0.0`; fine).
- Local DNS lag for a brand-new `*.trycloudflare.com` host: if `curl` says
  `Could not resolve host` (even though `dig +short <host>` returns an IP), wait a
  few seconds, or force it:
  ```sh
  IP=$(dig +short <host> | grep -E '^[0-9.]+$' | head -1)
  curl --resolve "<host>:443:$IP" "https://<host>/v1/models"
  ```
  The Fly gateway resolves it fine — this only affects the local machine.
