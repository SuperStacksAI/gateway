# RunPod GPU runs (cheap smoke -> dry run -> prod)

Start on a rented GPU; the rental is your first real test. Recommended: **cheap
smoke first** (a few cents), then scale. Exposure via **Cloudflare Tunnel**
(plan B) — see `cloudflared/`.

## Recommended sizes

| Purpose | GPU | Model | Image | Notes |
|---|---|---|---|---|
| Cheap smoke | 1x L4 / A10 / T4 / RTX 4090 | `Qwen/Qwen2.5-0.5B-Instruct` (~1GB) | `lmsysorg/sglang:latest` | proves `serve.sh` + full chain for cents |
| Dry run | 2x H200 | `deepseek-ai/DeepSeek-V4-Flash` (~170GB) | `lmsysorg/sglang:dev-dsv41` | real weights, flags, throughput |
| Prod-scale | 8x B300 / 8x H200 | `deepseek-ai/DeepSeek-V4.1-Flash-1017` (~510GB) | `lmsysorg/sglang:dev-dsv41` | see `recipe.md` |

## Storage (RunPod)

| Type | Persists | Cost | Use |
|---|---|---|---|
| Container disk | lost on stop | $0.10/GB/mo | tiny test (~1GB model) |
| Volume disk (`/workspace`) | until pod deleted | $0.10 running / $0.20 stopped | working files |
| **Network volume** (`/workspace`) | independent | **$0.07/GB/mo** | **weights** (attach at deploy; Secure Cloud) |

- Attach a **network volume at deploy** — it cannot be added later.
- ~510 GB for V4.1 ≈ **$36/mo**. Point `DEST`/`HF_CACHE` at `/workspace`.

## Cheap smoke (start here) — tiny model on 1 GPU

1. Rent a **1x L4 / A10 / T4 / 4090** pod, image `lmsysorg/sglang:latest`.
2. Serve the tiny model (SGLang pulls the ~1GB weights; no volume needed):

   ```sh
   MODEL_ID=Qwen/Qwen2.5-0.5B-Instruct \
   SERVED_NAME=qwen-tiny \
   IMAGE=lmsysorg/sglang:latest \
   TP_SIZE=1 EP_SIZE=1 CONTEXT_LENGTH=32768 MEM_FRACTION=0.80 \
   API_KEY="$(openssl rand -hex 24)" \
   ./serve.sh
   ```

3. Check: `API_KEY=<key> MODEL=qwen-tiny ./smoke.sh`
4. Expose it (quick tunnel, no account):
   ```sh
   MODE=quick SGLANG_PORT=30000 ./cloudflared/run-cloudflared.sh
   # copy the https://<random>.trycloudflare.com URL
   ```
5. Add a **temporary** LiteLLM entry (`model_name: selfhost-test`, `model:
   openai/qwen-tiny`, `api_base: https://<url>/v1`) — see `cloudflared/litellm-integration.md`.
6. Walk the chain: `MODEL=selfhost-test VIRTUAL_KEY=<vk> GATEWAY_BASE=https://<host> ./test-connection.sh`
7. Tear the pod down; delete the `selfhost-test` entry.

## Dry run / prod steps

1. **Create the pod** — GPU as above; **network volume** attached; note the image
   (`lmsysorg/sglang:dev-dsv41` for DeepSeek; `latest` for the tiny test).
2. **Download weights** (into the volume, ~510GB):
   ```sh
   pip install -U "huggingface_hub[cli]"
   MODEL_ID=deepseek-ai/DeepSeek-V4.1-Flash-1017 DEST=/workspace/hf ./download-weights.sh
   ```
3. **Serve** (prod defaults; set `TP_SIZE`/`EP_SIZE` per `recipe.md`):
   ```sh
   HF_CACHE=/workspace/hf API_KEY="$(openssl rand -hex 24)" ./serve.sh
   ```
4. **Check**: `API_KEY=<key> MODEL=deepseek-ai/DeepSeek-V4.1-Flash-1017 ./smoke.sh`
5. **Expose via Cloudflare Tunnel** (`cloudflared/run-cloudflared.sh`, quick or
   named per `cloudflared/README.md`).
6. **End-to-end through LiteLLM** — add the entry, fire a request, confirm the
   spend row.
7. **Tear down** the pod (and delete any temporary LiteLLM entry).

> Plan A (Tailscale relay) alternative: `relay/`.
