# Handoff: working with the colleague who rents the GPU

Division of labour (your choice "a"): the **colleague rents the pod and gives you
SSH access**; **you** run everything on it (weights, `serve.sh`, **cloudflared**)
via SSH — including the tunnel. Plan B = **Cloudflare Tunnel**, so there is **no
Tailscale and no relay**.

```
you (SSH) -> colleague's GPU pod: serve.sh (SGLang) + cloudflared
                     │  (outbound dial)
                     ▼
             Cloudflare edge  https://<tunnel-url>
                     ▲
your gateway (Fly) ──┘   api_base = https://<tunnel-url>/v1
```

## What you need FROM the colleague

1. **SSH access** to the pod: host/IP, port, user, and key (or a ready session).
2. **Pod spec**: GPU type/count, region/cloud, image.
3. **Storage decision**: if any DeepSeek run, a **network volume** attached at
   deploy (can't add later) — see `runpod.md`.
4. **Ownership of the run**: who keeps the pod alive; who tears it down; the
   **API key** (you generate it and share, or he does).

## What YOU run on the pod (via SSH)

```sh
# 1. (DeepSeek only) weights -> volume (~510GB)
pip install -U "huggingface_hub[cli]"
MODEL_ID=deepseek-ai/DeepSeek-V4.1-Flash-1017 DEST=/workspace/hf ./download-weights.sh

# 2. serve  (tiny example; prod = defaults + recipe.md flags)
MODEL_ID=Qwen/Qwen2.5-0.5B-Instruct SERVED_NAME=qwen-tiny \
IMAGE=lmsysorg/sglang:latest TP_SIZE=1 EP_SIZE=1 CONTEXT_LENGTH=32768 \
API_KEY="$(openssl rand -hex 24)" ./serve.sh

# 3. verify
API_KEY=<key> MODEL=qwen-tiny ./smoke.sh

# 4. expose (quick tunnel — no account)
MODE=quick SGLANG_PORT=30000 ./cloudflared/run-cloudflared.sh
#    -> copy https://<random>.trycloudflare.com
```

Record: the **tunnel URL**, the **API key**, the **served model name**.

## What you do on your side (no GPU)

1. Add the LiteLLM entry (`cloudflared/litellm-integration.md`):
   `api_base: https://<tunnel-url>/v1`, `api_key: os.environ/SELFHOST_DS_KEY`.
2. `fly secrets set SELFHOST_DS_KEY=<key> -a superstackai-gateway`.
3. Verify: `MODEL=<name> VIRTUAL_KEY=<vk> GATEWAY_BASE=https://<host> ./test-connection.sh`.
4. Confirm a spend row in LiteLLM.

## Message template to send the colleague

> I'll run everything on the pod over SSH. Please:
> 1. Rent the pod (see `selfhost/runpod.md`) and send me SSH details (host, port,
>    user, key) + the GPU type and region.
> 2. If it's a DeepSeek run, attach a **network volume** at deploy (~600 GB) and
>    mount it at `/workspace` — it can't be added later.
> 3. Keep it running until I confirm the end-to-end test passes; I'll tell you
>    when to tear it down.
> I'll handle weights, `serve.sh`, the Cloudflare tunnel, and the gateway wiring.

## Checklist (what you must end up with)
- [ ] SSH into the pod works.
- [ ] `smoke.sh` passes on the pod.
- [ ] Cloudflare tunnel URL captured.
- [ ] SGLang **API key** + **served name** captured.
- [ ] LiteLLM entry added; `test-connection.sh` green; spend row present.
- [ ] Pod torn down (when done).
