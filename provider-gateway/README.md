# Provider Gateway

OpenAI-compatible proxy that validates API keys from your OpenSaaS app and forwards requests to a third-party AI provider. No GPU needed.

```
User (sk-... key from your app) → Proxy → Provider API (Together / OpenAI / etc.)
                                       ↓
                                    Redis (rate limiting)
                                       ↓
                                    Postgres (key validation + usage tracking)
```

## Files

| File | Purpose |
|------|---------|
| `proxy/main.py` | FastAPI app — validates keys, proxies to provider, tracks usage |
| `proxy/requirements.txt` | Python dependencies |
| `Dockerfile.proxy` | Container build |
| `docker-compose.yml` | Local dev: proxy + Redis |
| `fly.toml` | Fly.io deployment config |
| `.env.example` | Environment variables template |

## Prerequisites

- **Postgres** database shared with your OpenSaaS app (must have `UsageLog` table)
- **Provider API key** — sign up at Together, OpenAI, Fireworks, Groq, etc.

## Local Dev

```bash
cp .env.example .env
# edit .env with your DATABASE_URL and PROVIDER_API_KEY

docker compose up -d
```

## Deploy to Fly.io

```bash
# Install flyctl if you haven't
brew install flyctl

# Launch app
fly launch --no-deploy

# Set secrets
fly secrets set DATABASE_URL="postgresql://..."
fly secrets set PROVIDER_BASE_URL="https://api.together.xyz/v1"
fly secrets set PROVIDER_API_KEY="tsk-..."
fly secrets set INPUT_PRICE_PER_M="0.15"
fly secrets set OUTPUT_PRICE_PER_M="0.60"
fly secrets set RPM_LIMIT="60"

# Optional: managed Redis on Fly
fly redis create
fly secrets set REDIS_URL="redis://..."

# Deploy
fly deploy
```

### Set your domain

```bash
fly certs create api.your-app.com
```

## How Users Connect

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...",  # created from your OpenSaaS frontend
    base_url="https://api.your-app.com/v1"
)
```

## Spin Up / Shut Down (to save cost)

```bash
# Stop all machines (stops billing)
fly scale count 0

# Start again
fly scale count 1
```

## Switching Providers

Just change the env vars — no code changes:

```bash
fly secrets set PROVIDER_BASE_URL="https://api.openai.com/v1" PROVIDER_API_KEY="sk-..."
fly deploy
```

## Cost

Runs on Fly.io's cheapest shared-CPU plan (~$5-15/mo). The main cost is whatever you're paying the provider — the proxy itself is negligible.
