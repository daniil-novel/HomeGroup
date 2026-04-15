from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
import uvicorn

from homegroup.application.services import HomeGroupService
from homegroup.infrastructure.ai import build_ai_client
from homegroup.infrastructure.config import Settings, get_settings
from homegroup.infrastructure.db.session import create_session_factory, ensure_schema
from homegroup.infrastructure.logging import configure_logging
from homegroup.infrastructure.telegram import (
    AiogramTelegramGateway,
    DisabledTelegramGateway,
    TelethonProvisioningService,
    run_polling_bot,
)
from homegroup.worker import HomeGroupWorker

app = typer.Typer(help="HomeGroup CLI")


def _service() -> tuple[HomeGroupService, Settings]:
    settings = get_settings()
    configure_logging(settings.debug)
    ensure_schema(settings)
    service = HomeGroupService(settings, build_ai_client(settings))
    return service, settings


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    uvicorn.run(
        "homegroup.presentation.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def worker() -> None:
    service, settings_obj = _service()
    settings = settings_obj
    gateway = AiogramTelegramGateway(settings) if settings.bot_token else DisabledTelegramGateway()
    HomeGroupWorker(settings, service, gateway).run()


@app.command()
def bot(drop_pending_updates: bool = False) -> None:
    service, settings_obj = _service()
    settings = settings_obj
    run_polling_bot(settings, service, drop_pending_updates=drop_pending_updates)


@app.command()
def provision() -> None:
    service, settings_obj = _service()
    settings = settings_obj
    typer.echo(TelethonProvisioningService(settings, service).provision())


@app.command()
def migrate() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


@app.command("backup-create")
def backup_create() -> None:
    service, settings_obj = _service()
    settings = settings_obj
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        typer.echo(str(service.create_backup(session)))


@app.command("backup-restore")
def backup_restore(archive: Path) -> None:
    service, settings_obj = _service()
    settings = settings_obj
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        service.restore_backup(session, archive)
    typer.echo(f"Restored {archive}")


@app.command()
def rebuild() -> None:
    service, settings_obj = _service()
    settings = settings_obj
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        service.ensure_defaults(session)
        typer.echo(str(service.diagnostics(session)))


@app.command()
def diagnostics() -> None:
    service, settings_obj = _service()
    settings = settings_obj
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        typer.echo(str(service.diagnostics(session)))
