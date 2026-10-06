# LiteLLM production image for Fly.io.
# The committed config contains no secrets; all secrets are injected at runtime
# via Fly secrets and referenced with LiteLLM's "os.environ/<VAR>" syntax.
FROM ghcr.io/berriai/litellm:main-stable

COPY config.fly.yaml /app/config.fly.yaml
COPY fly_entrypoint.sh /app/fly_entrypoint.sh
RUN chmod +x /app/fly_entrypoint.sh

ENV PORT=4000

EXPOSE 4000

ENTRYPOINT ["/app/fly_entrypoint.sh"]
CMD ["--config", "/app/config.fly.yaml", "--host", "0.0.0.0", "--port", "4000"]
