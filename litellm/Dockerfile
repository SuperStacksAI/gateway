# LiteLLM production image for Fly.io.
# The committed config contains no secrets; all secrets are injected at runtime
# via Fly secrets and referenced with LiteLLM's "os.environ/<VAR>" syntax.
FROM ghcr.io/berriai/litellm:main-stable

COPY config.fly.yaml /app/config.fly.yaml

ENV PORT=4000

EXPOSE 4000

CMD ["--config", "/app/config.fly.yaml", "--port", "4000"]
