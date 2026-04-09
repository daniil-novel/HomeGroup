# HomeGroup

HomeGroup is a production-oriented Telegram ecosystem for two people living together.
It includes:

- a Telegram bot;
- a provisioning agent for forum supergroup bootstrap;
- a server-rendered Telegram Mini App;
- a PostgreSQL-backed backend API;
- a worker for routines, reminders, summaries, exports and backups;
- an AI layer for parsing short free-form messages and generating concise summaries.

## Stack

- Python 3.11
- FastAPI
- aiogram
- Telethon
- SQLAlchemy 2 + Alembic
- Jinja2 + HTMX + Alpine.js
- PostgreSQL
- Docker Compose + Caddy
- uv / uvx
- ruff / mypy / pytest

## Quick start

```powershell
uv sync
uv run alembic upgrade head
uv run homegroup serve --reload
```

## Quality

```powershell
uvx --from . ruff check .
uvx --from . mypy src
uvx --from . pytest
```

## Main commands

```powershell
uv run homegroup serve
uv run homegroup worker
uv run homegroup provision
uv run homegroup migrate
uv run homegroup rebuild
uv run homegroup diagnostics
uv run homegroup backup-create
uv run homegroup backup-restore <archive>
```

## Deployment

Production deployment targets a Linux VPS with a public domain behind Caddy. See:

- `ops/compose.yaml`
- `ops/Caddyfile`
- `.env.example`
- `docs/deployment.md`
- `docs/operations.md`

