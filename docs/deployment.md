# Deployment

This deployment variant is intentionally **non-invasive** for a server that already runs `3x-ui`, VPN services and custom ports.

It does **not** bind `80`, `443`, `7443` or any VPN-related ports.

## Safe topology

- `app` listens inside Docker on `8000`
- host exposes it only on `127.0.0.1:18080`
- `worker` stays internal
- `postgres` stays internal
- the existing host-level reverse proxy must forward a separate public hostname to `http://127.0.0.1:18080`

Do **not** use the current `3x-ui` panel URL like `https://novel-cloudtech.com:7443/login` as the Mini App or webhook URL.

Use one of these instead:

1. a separate subdomain, recommended:
   `https://homegroup.novel-cloudtech.com`
2. a separate host/path in the existing reverse proxy, only if you are sure it does not interfere with the panel

## Steps

1. Prepare a separate public domain or subdomain for HomeGroup.
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

6. Add a reverse proxy rule on the existing server config so the chosen HomeGroup hostname points to `http://127.0.0.1:18080`.
7. Set Telegram webhook to `https://<homegroup-domain>/telegram/webhook`.
8. Run provisioning:

```bash
docker compose -f ops/compose.yaml exec app uv run homegroup provision
```

## Example Nginx reverse proxy snippet

See `ops/nginx-homegroup.conf.example`.

## Important

- do not replace existing `server` blocks used by `3x-ui`
- do not move `3x-ui` off `7443`
- do not reuse VPN ports
- HomeGroup should be added as a separate hostname routed to `127.0.0.1:18080`

The current VPS `91.84.104.36` still needs a healthy SSH daemon before I can automate the real deployment from here.
