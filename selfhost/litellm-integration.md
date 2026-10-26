# Wiring the self-hosted model into LiteLLM

The gateway app is **untouched**. You only add/repoint a model entry
(`store_model_in_db: true` is already on, so no redeploy).

## 1. Store the upstream key as a Fly secret

The SGLang `API_KEY` (from `selfhost/.env`) becomes the upstream key:

```sh
fly secrets set SELFHOST_DS_KEY=<the SGLang API_KEY> -a superstackai-gateway
```

## 2. Add the model entry (UI or API)

Via the LiteLLM UI (`models` -> add model) or the Admin API:

```json
{
  "model_name": "deepseek-v4.1",
  "litellm_params": {
    "model": "openai/deepseek-ai/DeepSeek-V4.1-Flash",
    "api_base": "http://selfhost-relay.internal:8080/v1",
    "api_key": "os.environ/SELFHOST_DS_KEY"
  },
  "model_info": {
    "input_cost_per_token": 0.0,
    "output_cost_per_token": 0.0
  }
}
```

`api_base` uses Fly 6PN (`.internal`) so traffic never leaves Fly's private
network until it hits the relay. Set `input/output_cost_per_token` to your
internal "price" so the credits/spend system keeps working.

## 3. Verify

```sh
curl -sS https://<gateway-host>/v1/chat/completions \
  -H "Authorization: Bearer <virtual-key>" \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4.1","messages":[{"role":"user","content":"hi"}]}'
```

Virtual keys are `["*"]`, so every existing user can call `deepseek-v4.1`
immediately — no key or app changes.

## 4. Switching models later (V4-Flash -> V4.1-Flash -> V4-Pro)

Only two edits, no app change:

1. `selfhost/.env`: change `MODEL_ID` (and parallel/KV flags), restart `serve.sh`.
2. This entry's `model` / `api_base` if the served name changes.

The user-facing `model_name` (`deepseek-v4.1`) can stay stable, so users are
unaffected.

## Notes

- The UI login is the **master key** (`LITELLM_MASTER_KEY` Fly secret), not a
  separate username/password.
- To change the upstream key later: `fly secrets set SELFHOST_DS_KEY=<new>`.
