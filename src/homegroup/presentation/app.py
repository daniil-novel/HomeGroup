from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from homegroup.application.schemas import (
    ChoreCreateForm,
    DailyPlanForm,
    DecisionCreateForm,
    EventCreateForm,
    NoteCreateForm,
    PurchaseCreateForm,
    SearchResult,
    SettingsUpdateForm,
    WeeklyPlanForm,
)
from homegroup.application.services import HomeGroupService
from homegroup.domain.enums import ChoreFrequency, ChoreMode, ChoreType, PayerMode, PurchaseCategory
from homegroup.infrastructure.ai import build_ai_client
from homegroup.infrastructure.config import Settings, get_settings
from homegroup.infrastructure.db.models import Chore, Decision, Event, Note, Purchase, SystemSetting
from homegroup.infrastructure.db.session import create_session_factory, ensure_schema
from homegroup.infrastructure.logging import configure_logging
from homegroup.infrastructure.telegram import build_dispatcher, handle_update
from homegroup.presentation.auth import verify_telegram_init_data

templates = Jinja2Templates(directory="templates")


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.debug)
    session_factory = create_session_factory(active_settings)
    service = HomeGroupService(active_settings, build_ai_client(active_settings))
    dispatcher = build_dispatcher(active_settings, service)

    app = FastAPI(title=active_settings.app_name)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.state.settings = active_settings
    app.state.session_factory = session_factory
    app.state.service = service
    app.state.dispatcher = dispatcher

    @app.on_event("startup")
    async def startup() -> None:
        ensure_schema(active_settings)
        with session_factory() as session:
            service.ensure_defaults(session)

    def get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def require_webapp(request: Request) -> None:
        init_data = request.headers.get("X-Telegram-Init-Data", "") or request.query_params.get(
            "initData", ""
        )
        if not verify_telegram_init_data(init_data, active_settings):
            raise HTTPException(status_code=401, detail="Mini App authorization failed.")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/mini-app/dashboard")

    @app.get("/health/live")
    async def health_live() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/health/ready")
    async def health_ready(session: Session = Depends(get_session)) -> JSONResponse:
        diagnostics = service.diagnostics(session)
        return JSONResponse({"status": "ok", "details": diagnostics})

    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request) -> JSONResponse:
        await handle_update(dispatcher, active_settings, await request.json())
        return JSONResponse({"ok": True})

    @app.get("/mini-app/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            _context(
                service=service,
                session=session,
                title="Dashboard",
                screen="dashboard",
                extra={"dashboard": service.dashboard(session)},
            ),
        )

    @app.get("/mini-app/today", response_class=HTMLResponse)
    async def today_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "today.html",
            _context(service, session, "Today Planner", "today"),
        )

    @app.post("/mini-app/today")
    async def save_today(
        request: Request,
        user_id: str = Form(...),
        date_value: str = Form(...),
        location: str = Form(""),
        busy_from: str = Form(""),
        busy_to: str = Form(""),
        after_work: str = Form(""),
        important_today: str = Form(""),
        joint_plan: str = Form(""),
        shopping_today: str = Form(""),
        household_evening: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.upsert_daily_plan(
            session,
            DailyPlanForm(
                user_id=user_id,
                date=date.fromisoformat(date_value),
                location=location or None,
                busy_from=time.fromisoformat(busy_from) if busy_from else None,
                busy_to=time.fromisoformat(busy_to) if busy_to else None,
                after_work=after_work or None,
                important_today=important_today or None,
                joint_plan=joint_plan or None,
                shopping_today=shopping_today or None,
                household_evening=household_evening or None,
            ),
        )
        return RedirectResponse("/mini-app/today", status_code=303)

    @app.get("/mini-app/week", response_class=HTMLResponse)
    async def week_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "week.html",
            _context(service, session, "Week Planner", "week"),
        )

    @app.post("/mini-app/week")
    async def save_week(
        request: Request,
        week_start: str = Form(...),
        summary: str = Form(""),
        goals: str = Form(""),
        joint_plans: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.upsert_weekly_plan(
            session,
            WeeklyPlanForm(
                week_start=date.fromisoformat(week_start),
                summary=summary or None,
                goals=[item.strip() for item in goals.splitlines() if item.strip()],
                joint_plans=[item.strip() for item in joint_plans.splitlines() if item.strip()],
            ),
        )
        return RedirectResponse("/mini-app/week", status_code=303)

    @app.get("/mini-app/calendar", response_class=HTMLResponse)
    async def calendar_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "entities.html",
            _context(
                service,
                session,
                "Calendar",
                "calendar",
                {
                    "items": session.scalars(select(Event).order_by(Event.date.desc())).all(),
                    "form_action": "/mini-app/calendar",
                },
            ),
        )

    @app.post("/mini-app/calendar")
    async def create_event(
        request: Request,
        owner_user_id: str = Form(...),
        title: str = Form(...),
        category: str = Form(...),
        date_value: str = Form(...),
        start_at: str = Form(""),
        end_at: str = Form(""),
        location: str = Form(""),
        is_joint: bool = Form(False),
        notes: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.create_event(
            session,
            EventCreateForm(
                owner_user_id=owner_user_id,
                title=title,
                category=category,
                date=date.fromisoformat(date_value),
                start_at=datetime.fromisoformat(start_at) if start_at else None,
                end_at=datetime.fromisoformat(end_at) if end_at else None,
                location=location or None,
                is_joint=is_joint,
                notes=notes or None,
            ),
        )
        return RedirectResponse("/mini-app/calendar", status_code=303)

    @app.get("/mini-app/purchases", response_class=HTMLResponse)
    async def purchases_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "entities.html",
            _context(
                service,
                session,
                "Purchases",
                "purchases",
                {
                    "items": session.scalars(select(Purchase).order_by(Purchase.created_at.desc())).all(),
                    "form_action": "/mini-app/purchases",
                },
            ),
        )

    @app.post("/mini-app/purchases")
    async def create_purchase(
        request: Request,
        created_by: str = Form(...),
        title: str = Form(...),
        category: str = Form(...),
        description: str = Form(""),
        budget_amount: str = Form(""),
        currency: str = Form("RUB"),
        payer_mode: str = Form("separate_no_split"),
        driver_user_id: str = Form(""),
        approver_user_id: str = Form(""),
        deadline_at: str = Form(""),
        notes: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.create_purchase(
            session,
            PurchaseCreateForm(
                title=title,
                category=PurchaseCategory(category),
                description=description or None,
                budget_amount=Decimal(budget_amount) if budget_amount else None,
                currency=currency,
                payer_mode=PayerMode(payer_mode),
                driver_user_id=driver_user_id or None,
                approver_user_id=approver_user_id or None,
                deadline_at=datetime.fromisoformat(deadline_at) if deadline_at else None,
                notes=notes or None,
            ),
            created_by=created_by,
        )
        return RedirectResponse("/mini-app/purchases", status_code=303)

    @app.get("/mini-app/chores", response_class=HTMLResponse)
    async def chores_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "entities.html",
            _context(
                service,
                session,
                "Chores",
                "chores",
                {
                    "items": session.scalars(select(Chore).order_by(Chore.created_at.desc())).all(),
                    "form_action": "/mini-app/chores",
                },
            ),
        )

    @app.post("/mini-app/chores")
    async def create_chore(
        request: Request,
        title: str = Form(...),
        chore_type: str = Form(...),
        frequency: str = Form("once"),
        mode: str = Form(...),
        due_at: str = Form(""),
        assigned_user_id: str = Form(""),
        backup_user_id: str = Form(""),
        estimated_minutes: int | None = Form(None),
        notes: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.create_chore(
            session,
            ChoreCreateForm(
                title=title,
                chore_type=ChoreType(chore_type),
                frequency=ChoreFrequency(frequency),
                mode=ChoreMode(mode),
                due_at=datetime.fromisoformat(due_at) if due_at else None,
                assigned_user_id=assigned_user_id or None,
                backup_user_id=backup_user_id or None,
                estimated_minutes=estimated_minutes,
                notes=notes or None,
            ),
        )
        return RedirectResponse("/mini-app/chores", status_code=303)

    @app.get("/mini-app/decisions", response_class=HTMLResponse)
    async def decisions_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "entities.html",
            _context(
                service,
                session,
                "Decisions",
                "decisions",
                {
                    "items": session.scalars(select(Decision).order_by(Decision.created_at.desc())).all(),
                    "form_action": "/mini-app/decisions",
                },
            ),
        )

    @app.post("/mini-app/decisions")
    async def create_decision(
        request: Request,
        question: str = Form(...),
        options: str = Form(""),
        driver_user_id: str = Form(""),
        approver_user_id: str = Form(""),
        deadline_at: str = Form(""),
        rationale_short: str = Form(""),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.create_decision(
            session,
            DecisionCreateForm(
                question=question,
                options=[item.strip() for item in options.splitlines() if item.strip()],
                driver_user_id=driver_user_id or None,
                approver_user_id=approver_user_id or None,
                deadline_at=datetime.fromisoformat(deadline_at) if deadline_at else None,
                rationale_short=rationale_short or None,
            ),
        )
        return RedirectResponse("/mini-app/decisions", status_code=303)

    @app.get("/mini-app/notes", response_class=HTMLResponse)
    async def notes_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        notes = session.scalars(select(Note).order_by(Note.created_at.desc())).all()
        suggestions = {
            note.id: service.note_conversion_suggestion(note.text)
            for note in notes
        }
        return templates.TemplateResponse(
            request,
            "notes.html",
            _context(
                service,
                session,
                "Notes / Inbox",
                "notes",
                {"items": notes, "suggestions": suggestions},
            ),
        )

    @app.post("/mini-app/notes")
    async def create_note(
        request: Request,
        created_by: str = Form(...),
        text_value: str = Form(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.create_note(session, NoteCreateForm(text=text_value, created_by=created_by))
        return RedirectResponse("/mini-app/notes", status_code=303)

    @app.get("/mini-app/archive", response_class=HTMLResponse)
    async def archive_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        archived = {
            "purchases": session.scalars(
                select(Purchase).where(Purchase.status == "archived")
            ).all(),
            "chores": session.scalars(select(Chore).where(Chore.status == "archived")).all(),
            "decisions": session.scalars(
                select(Decision).where(Decision.status == "archived")
            ).all(),
            "notes": session.scalars(select(Note).where(Note.status == "archived")).all(),
        }
        return templates.TemplateResponse(
            request,
            "archive.html",
            _context(service, session, "Archive", "archive", {"archived": archived}),
        )

    @app.get("/mini-app/settings", response_class=HTMLResponse)
    async def settings_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "settings.html",
            _context(
                service,
                session,
                "Settings",
                "settings",
                {
                    "items": session.scalars(
                        select(SystemSetting).order_by(SystemSetting.key.asc())
                    ).all()
                },
            ),
        )

    @app.post("/mini-app/settings")
    async def save_settings(
        request: Request,
        payload: str = Form(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        service.update_system_settings(session, SettingsUpdateForm(values=json.loads(payload)))
        return RedirectResponse("/mini-app/settings", status_code=303)

    @app.get("/mini-app/analytics", response_class=HTMLResponse)
    async def analytics_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        dashboard_data = service.dashboard(session)
        analytics = {
            "pending_purchases": len(dashboard_data.pending_purchases),
            "chores_today": len(dashboard_data.chores_today),
            "pending_decisions": len(dashboard_data.pending_decisions),
            "notes_inbox": len(dashboard_data.notes_inbox),
        }
        return templates.TemplateResponse(
            request,
            "analytics.html",
            _context(service, session, "Analytics", "analytics", {"analytics": analytics}),
        )

    @app.get("/mini-app/templates", response_class=HTMLResponse)
    async def templates_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        return templates.TemplateResponse(
            request,
            "templates_manager.html",
            _context(service, session, "Templates", "templates"),
        )

    @app.get("/mini-app/automation", response_class=HTMLResponse)
    async def automation_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        diagnostics = service.diagnostics(session)
        return templates.TemplateResponse(
            request,
            "automation.html",
            _context(
                service,
                session,
                "Automation Rules",
                "automation",
                {"diagnostics": diagnostics},
            ),
        )

    @app.get("/mini-app/backups", response_class=HTMLResponse)
    async def backups_screen(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
        require_webapp(request)
        backups = sorted(active_settings.backup_dir.glob("*.zip"), reverse=True)
        return templates.TemplateResponse(
            request,
            "backups.html",
            _context(service, session, "Backups / Export", "backups", {"backups": backups}),
        )

    @app.post("/mini-app/backups/create")
    async def create_backup(request: Request, session: Session = Depends(get_session)) -> RedirectResponse:
        require_webapp(request)
        service.create_backup(session)
        return RedirectResponse("/mini-app/backups", status_code=303)

    @app.post("/mini-app/backups/restore")
    async def restore_backup(
        request: Request,
        archive: UploadFile = File(...),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        require_webapp(request)
        filename = archive.filename or "restore.zip"
        target = active_settings.backup_dir / filename
        target.write_bytes(await archive.read())
        service.restore_backup(session, target)
        return RedirectResponse("/mini-app/backups", status_code=303)

    @app.get("/api/v1/search", response_model=list[SearchResult])
    async def search(query: str, session: Session = Depends(get_session)) -> list[SearchResult]:
        return service.search(session, query)

    @app.post("/api/v1/export")
    async def export(session: Session = Depends(get_session)) -> JSONResponse:
        bundle = service.export_bundle(session)
        return JSONResponse(bundle.payload)

    @app.post("/api/v1/backups/create")
    async def api_backup_create(session: Session = Depends(get_session)) -> JSONResponse:
        archive_path = service.create_backup(session)
        return JSONResponse({"archive": str(archive_path)})

    @app.post("/api/v1/backups/restore")
    async def api_backup_restore(
        archive_path: str = Form(...),
        session: Session = Depends(get_session),
    ) -> JSONResponse:
        service.restore_backup(session, Path(archive_path))
        return JSONResponse({"status": "restored"})

    return app


def _context(
    service: HomeGroupService,
    session: Session,
    title: str,
    screen: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = {
        "title": title,
        "screen": screen,
        "settings": {item.key: item.value_json for item in session.scalars(select(SystemSetting)).all()},
        "dashboard_nav": service.dashboard(session),
    }
    if extra:
        context.update(extra)
    return context
