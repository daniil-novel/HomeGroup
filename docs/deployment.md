# Deployment

1. Prepare a public domain or subdomain for the VPS.
2. Install Docker Engine and Docker Compose plugin.
3. Copy `.env.example` to `.env` and fill in Telegram and OpenRouter secrets.
4. Run:

```bash
docker compose -f ops/compose.yaml up --build -d
```

5. Apply migrations:

```bash
docker compose -f ops/compose.yaml exec app uv run alembic upgrade head
```

6. Set Telegram webhook to `https://<domain>/telegram/webhook`.
7. Run provisioning:

```bash
docker compose -f ops/compose.yaml exec app uv run homegroup provision
```

The current VPS `91.84.104.36` still needs a healthy SSH daemon before remote bootstrap can be automated.

