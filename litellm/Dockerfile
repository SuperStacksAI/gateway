# LiteLLM production image for Fly.io.
# The committed config contains no secrets; all secrets are injected at runtime
# via Fly secrets and referenced with LiteLLM's "os.environ/<VAR>" syntax.
FROM ghcr.io/berriai/litellm:main-stable

COPY config.fly.yaml /app/config.fly.yaml

ENV PORT=4000

EXPOSE 4000

# Listen on 0.0.0.0 (IPv4), which is what Fly's edge proxy connects to for both
# public ingress and private Flycast. Direct 6PN (.internal) is IPv6-only, and
# LiteLLM/uvicorn binds IPv4, so the app reaches this over the public HTTPS URL
# (authenticated with the master key) instead.
CMD ["--config", "/app/config.fly.yaml", "--host", "0.0.0.0", "--port", "4000"]
