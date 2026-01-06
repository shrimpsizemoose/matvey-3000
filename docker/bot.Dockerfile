FROM python:3.11-slim-bookworm AS builder

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /uvx /bin/

WORKDIR /bot

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies with uv (frozen for reproducibility, no dev deps)
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev --no-install-project

# Copy source files
COPY src/ ./src/
COPY scripts/ ./scripts/


FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.source https://github.com/shrimpsizemoose/matvey-3000

ARG GIT_SHA
ENV GIT_SHA_ENV=$GIT_SHA

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 10001 --no-create-home --shell /bin/false matvey

WORKDIR /bot

# Copy virtual environment from builder
COPY --from=builder /bot/.venv /bot/.venv

# Copy source files
COPY --from=builder /bot/src ./src
COPY --from=builder /bot/scripts ./scripts

# Set ownership and switch to non-root user
RUN chown -R matvey:matvey /bot
USER matvey

# Add venv to path
ENV PATH="/bot/.venv/bin:$PATH"

CMD ["python", "src/bot.py"]
