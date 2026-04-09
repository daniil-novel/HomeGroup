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

Open the server-rendered Mini App at `http://127.0.0.1:8000/mini-app/dashboard`.

## Quality

```powershell
uvx --from . ruff check .
uvx --from . mypy src
uvx --from . pytest
```

## What is implemented

- domain model for users, chats, topics, plans, events, purchases, chores, decisions, notes, reminders, message links, templates, automation rules, settings, audit log and health;
- Alembic migrations for the initial schema and settings tables;
- FastAPI app with health checks, Telegram webhook, Mini App screens and internal API endpoints;
- server-rendered screens for Dashboard, Today, Week, Calendar, Purchases, Chores, Decisions, Notes, Archive, Settings, Analytics, Templates, Automation and Backups;
- aiogram command router for the required bot commands;
- Telethon-based provisioning service for forum chat bootstrap and topic creation;
- OpenRouter-backed AI client with deterministic fallback classification and summaries;
- worker with morning/evening/weekly jobs, diagnostics and periodic backups;
- backup/export/restore flow with JSON, Markdown and ZIP archives.

## Local development

```powershell
uv sync
uv run alembic upgrade head
uv run homegroup diagnostics
uv run homegroup serve --reload
```

Useful URLs:

- `GET /health/live`
- `GET /health/ready`
- `/mini-app/dashboard`
- `/api/v1/search?query=...`
- `/api/v1/export`

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
- `docs/telegram-setup.md`

## Notes

- Provisioning requires real Telegram credentials and an interactive owner login on the first run.
- The current target VPS `91.84.104.36` still has an SSH daemon problem: TCP on port `22` is reachable, but the connection breaks before normal authentication completes, so remote bootstrap is not automated yet.

## To see the real Telegram group

1. Fill `.env` with real Telegram, OpenRouter and domain values.
2. Deploy the stack and run migrations.
3. Configure the bot in BotFather and point the webhook to your public domain.
4. Run `uv run homegroup provision`.
5. During the first provisioning run, confirm the Telegram login for the owner account.
6. After provisioning finishes, open Telegram under the owner account and look for the new private forum supergroup named `Дом`.
7. The second user will see the same group after being invited and accepting the invite.
