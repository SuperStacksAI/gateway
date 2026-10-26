# Pinned SGLang recipes (DeepSeek V4.1)

Concrete, verified launch configs so the first GPU run works. Sources: SGLang
cookbook (DeepSeek-V4.1), HF model card, vLLM recipes. **Re-check before prod** —
V4.1 support is preview and moves fast.

## Image

⚠️ **V4.1 has not shipped in an SGLang release yet** — use the preview image:

```
lmsysorg/sglang:dev-dsv41     # H200 / B200 / B300 / GB300
```

The tiny test uses the standard `lmsysorg/sglang:latest`.

## Checkpoints

| Checkpoint | Notes |
|---|---|
| `deepseek-ai/DeepSeek-V4.1-Flash-1017` | **recommended** (2026-10-17 update) |
| `deepseek-ai/DeepSeek-V4.1-Flash` | 0909 launch release |

- License: **MIT** (public, no HF token required).
- Repo size: **~510 GB**.
- Arch: `model_type: deepseek_v4.1`, backend `dsv4`; 40 decoder layers, 384 routed
  experts (top-6) + 1 shared; fp8 dense (ue8m0, 32-wide block) + **fp4 routed
  experts**; DSpark speculative head. Global KV **890 B/token** (FP4 E2M1).
- `vram_minimum_gb: 614` → fits one GB200 NVL4 tray (768 GB) at TP4, or one
  8×H200 node (1128 GB).

## B300 (verified) — 4× B300, TP4 + EP4

Same recipe as GB300 (kernels dispatch by architecture family).

```sh
python3 -m sglang.launch_server \
  --model-path deepseek-ai/DeepSeek-V4.1-Flash-1017 \
  --served-model-name deepseek-ai/DeepSeek-V4.1-Flash-1017 \
  --trust-remote-code \
  --tp-size 4 --ep-size 4 \
  --attention-backend dsv4 \
  --enable-deepseek-v4-fp4-indexer \
  --kv-cache-dtype fp8_e4m3 \
  --page-size 256 \
  --swa-full-tokens-ratio 0.15 \
  --mem-fraction-static 0.92 \
  --chunked-prefill-size 16384 \
  --cuda-graph-max-bs-decode 64 \
  --speculative-algorithm DSPARK \
  --speculative-dspark-block-size 5 \
  --host 0.0.0.0 --port 30000
```

Env equivalents for `serve.sh`: `MODEL_ID=…-1017`, `IMAGE=lmsysorg/sglang:dev-dsv41`,
`MEM_FRACTION=0.92`, `CHUNKED_PREFILL=16384`, and the `EXTRA_ARGS` in `.env.example`.

**Hard constraint:** no context parallelism on decode — **CP=1, DCP=1**. Any other
combination is rejected at startup. `SGLANG_RAGGED_VERIFY_MODE=static` (default).

### OPEN DECISION — our node is 8× B300

The verified recipe is **4 GPUs**. For 8× B300, choose one:

| Option | Layout | Notes |
|---|---|---|
| **A. Single TP8** | 1 server across 8 GPUs (`TP_SIZE=8 EP_SIZE=8`) | simplest; unverified for V4.1 |
| **B. Two TP4·EP4 replicas** | 2 servers × 4 GPUs, behind SGLang's router (`--router-mode kv`) | matches the verified recipe; more robust |

Decide before the production run; set `TP_SIZE`/`EP_SIZE` accordingly.

## T4 tiny test (plumbing only)

```sh
python3 -m sglang.launch_server \
  --model-path Qwen/Qwen2.5-0.5B-Instruct \
  --served-model-name qwen-tiny \
  --host 0.0.0.0 --port 30000 \
  --tp-size 1 --ep-size 1 \
  --context-length 32768 \
  --mem-fraction-static 0.80
```

No `EXTRA_ARGS`, `IMAGE=lmsysorg/sglang:latest`. (~6–8 GB VRAM.)

## Caveats

- **FP4 kernels are Blackwell-native.** B300/B200/GB300 are the target; other
  arch families may be unsupported or slow.
- Preview image/tag can move — pin a digest once verified.
- For KV offload (long context), the cookbook offers HiCache (host DRAM) or a
  Mooncake store via the external linker.
- If `--speculative-algorithm DSPARK` crash-loops at warmup (seen on some archs),
  drop the DSpark flags first and retest.
