FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY templates ./templates
COPY static ./static

RUN uv sync --frozen --no-dev || uv sync --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["uv", "run", "homegroup", "serve", "--host", "0.0.0.0", "--port", "8000"]

