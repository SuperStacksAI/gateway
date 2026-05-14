# LLM Gateway

OpenAI-compatible proxy for serving MiniMax 2.7 (or any vLLM model) with API key auth, rate limiting, and usage tracking. Integrates with your OpenSaaS database for key validation and billing.

## Architecture

```
User → Proxy (port 8080) → vLLM (port 8001)
         ↓
      Redis (rate limiting)
         ↓
      Postgres (key validation + usage logs ← shared with OpenSaaS app)
```

## Files

| File | Purpose |
|------|---------|
| `proxy/main.py` | FastAPI app — validates API keys, proxies to vLLM, tracks usage |
| `proxy/requirements.txt` | Python dependencies |
| `Dockerfile.proxy` | Builds the proxy container |
| `docker-compose.yml` | Orchestrates vLLM + proxy + Redis |
| `.env.example` | Environment variables template |

## What You Need to Edit Before Deployment

### 1. `docker-compose.yml` — the vLLM model

If you're **not** using MiniMax, change `VLLM_MODEL` in the environment section (line 15):

```yaml
- MODEL_NAME=minimax-2.7                    # ← name users will send in their API requests
- VLLM_MODEL=minimax/MiniMax-M2             # ← actual HuggingFace model path
```

If the model needs a different GPU config, adjust:

```yaml
- TENSOR_PARALLEL_SIZE=1       # increase for multi-GPU
- GPU_MEMORY_UTILIZATION=0.9   # reduce if OOM
- MAX_MODEL_LEN=8192           # reduce if VRAM is tight
```

### 2. `.env` — database and pricing (create this file from `.env.example`)

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Your Postgres connection string (same one your OpenSaaS app uses)
DATABASE_URL=postgresql://user:password@host:5432/opensaas

# Per-1M-token pricing (adjust to your margins)
INPUT_PRICE_PER_M=0.15
OUTPUT_PRICE_PER_M=0.60

# Rate limits per user
RPM_LIMIT=60
TPM_LIMIT=300000
```

### 3. `proxy/main.py` — pricing (optional)

If you want per-model pricing instead of global env vars, edit the pricing logic in the proxy (around line 146-148).

## Prerequisites

- **GPU machine** with NVIDIA drivers and Docker + nvidia-container-toolkit installed
- **Postgres database** shared with your OpenSaaS app (with the `UsageLog` table — see migration in `ssAI-fe-be-db`)
- **Redis** (started automatically by Docker Compose)

## Deployment Steps

### 1. Set up the database

Run the migration in your OpenSaaS project to create the `UsageLog` table:

```bash
cd ../ssAI-fe-be-db/template/app
wasp db migrate
```

Or apply the raw SQL directly:

```bash
psql $DATABASE_URL < app/migrations/20260515000000_add_usagelog/migration.sql
```

### 2. Configure environment

```bash
cp .env.example .env
# edit .env with your DATABASE_URL and pricing
```

### 3. Start the stack

```bash
docker compose up -d
```

This starts:
- **vLLM** on port 8001 (internal, serving your model)
- **Proxy** on port 8080 (exposed to users)
- **Redis** on port 6379 (internal)

### 4. Verify

```bash
curl http://localhost:8080/health
# → {"status": "ok"}

# Test with an API key from your OpenSaaS frontend
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "minimax-2.7", "messages": [{"role": "user", "content": "hello"}]}'
```

### 5. Expose to users

Point your domain (e.g., `api.your-app.com`) to the proxy on port 8080. Users connect with the OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...",
    base_url="https://api.your-app.com/v1"
)
```

## Monitoring

- Usage data is written to the `UsageLog` table — query it from your frontend dashboard
- Rate limit counters live in Redis (`ratelimit:rpm:{user_id}`) — `redis-cli keys 'ratelimit:*'`

## Updating the Model

```bash
# Stop, rebuild, and restart
docker compose down
# edit VLLM_MODEL in .env
docker compose up -d
```

## Cost

The only real cost is the GPU. MiniMax 2.7 is small — an **A10 (24GB)** is plenty.

| Option | Cost/mo | Notes |
|--------|---------|-------|
| Spot GPU (Vast.ai, RunPod) | ~$150–350 | Best for production |
| On-demand (Lambda, RunPod) | ~$400–800 | Predictable, no preemption |
| Dev/testing spot (Vast.ai) | ~$20–40 | Spin up a few hours a day |

Postgres, Redis, and the proxy add ~$0 if they share your existing infra. At 200 users × $10/mo = **$2000/mo revenue**.

## Dev / Testing Spin Up & Shut Down

```bash
# Start
docker compose pull     # pull latest vLLM image
docker compose up -d    # start everything

# Verify
curl http://localhost:8080/health

# Shut down (stops billing on spot GPU)
docker compose down

# Full cleanup (wipes model from GPU memory)
docker compose down --volumes
```
