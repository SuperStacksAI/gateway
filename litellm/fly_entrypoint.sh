#!/bin/sh
set -e

# LiteLLM/uvicorn binds IPv4 (0.0.0.0), which is what Fly's public edge proxy
# uses. Fly's 6PN private network (.internal) is IPv6-only, so we run an
# IPv6-only listener on [::]:4000 that forwards to LiteLLM's IPv4 listener.
# This lets the app talk to the Admin API privately (master key never crosses
# the public internet) while customers keep hitting the public /v1 endpoint.
python - <<'PY' &
import asyncio
import socket


async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_reader, client_writer):
    try:
        up_reader, up_writer = await asyncio.open_connection("127.0.0.1", 4000)
    except Exception:
        client_writer.close()
        return
    await asyncio.gather(
        pipe(client_reader, up_writer),
        pipe(up_reader, client_writer),
    )


async def main():
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.bind(("::", 4000))
    sock.listen(128)
    server = await asyncio.start_server(handle, sock=sock)
    async with server:
        await server.serve_forever()


asyncio.run(main())
PY

exec litellm "$@"
