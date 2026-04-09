# Operations

## Health checks

- `GET /health/live`
- `GET /health/ready`

## Backups

Create a backup:

```bash
uv run homegroup backup-create
```

Restore a backup:

```bash
uv run homegroup backup-restore backups/<archive>.zip
```

## Diagnostics

```bash
uv run homegroup diagnostics
```

## Quality gates

```bash
uvx --from . ruff check .
uvx --from . mypy src
uvx --from . pytest
```

