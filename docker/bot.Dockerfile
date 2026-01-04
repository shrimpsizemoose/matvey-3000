FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.source https://github.com/shrimpsizemoose/matvey-3000

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /bot

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock /bot/

# Install dependencies with uv (frozen for reproducibility, no dev deps)
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev

COPY src/bot_handler.py  /bot/
COPY src/config.py /bot/
COPY src/chat_completions.py /bot/
COPY src/message_store.py /bot/
COPY scripts/dump_data_from_storage.py /bot/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG GIT_SHA
ENV GIT_SHA_ENV=$GIT_SHA

CMD ["uv", "run", "python", "/bot/bot_handler.py"]
