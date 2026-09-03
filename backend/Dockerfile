# Orion backend. Explicit Dockerfile rather than Nixpacks autodetection: the
# project is uv-managed and pinned to Python 3.12, and the start command needs
# to bind Railway's $PORT.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first, so a code change doesn't reinstall the world.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# The websocket bridges are the whole product, so this must be an ASGI server
# with websocket support - uvicorn[standard] is already a dependency.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
