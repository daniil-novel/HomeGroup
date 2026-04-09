from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import JSON as SAJSON
from sqlalchemy import Boolean as SABoolean
from sqlalchemy import Date as SADate
from sqlalchemy import DateTime as SADateTime
from sqlalchemy import Numeric as SANumeric
from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy import Time as SATime
from sqlalchemy.orm import Session

from homegroup.application.bootstrap import BUILTIN_TEMPLATES
from homegroup.application.ports import AIClient
from homegroup.application.schemas import (
    ChoreCreateForm,
    DailyPlanForm,
    DashboardView,
    DecisionCreateForm,
    EventCreateForm,
    NoteCreateForm,
    PurchaseCreateForm,
    SearchResult,
    SettingsUpdateForm,
    WeeklyPlanForm,
)
from homegroup.domain.enums import (
    AIClassification,
    AutomationMode,
    ChoreStatus,
    DecisionStatus,
    EventStatus,
    HealthStatus,
    NoteStatus,
    PurchaseStatus,
)
from homegroup.domain.rules import (
    BalanceSnapshot,
    choose_chore_assignee,
    purchase_requires_confirmation,
)
from homegroup.infrastructure.config import Settings
from homegroup.infrastructure.db.base import Base
from homegroup.infrastructure.db.models import (
    AuditLog,
    AutomationRule,
    Chat,
    Chore,
    DailyPlan,
    Decision,
    Event,
    MessageLink,
    Note,
    Purchase,
    Reminder,
    SystemHealth,
    SystemSetting,
    Template,
    Topic,
    User,
    UserSetting,
    WeeklyPlan,
)


@dataclass(slots=True)
class ExportBundle:
    payload: dict[str, list[dict[str, object]]]
    markdown: str
    archive_path: Path | None = None


class HomeGroupService:
    def __init__(self, settings: Settings, ai_client: AIClient) -> None:
        self.settings = settings
        self.ai_client = ai_client

    def ensure_defaults(self, session: Session) -> None:
        for slug, (title, body) in BUILTIN_TEMPLATES.items():
            if session.scalar(select(Template).where(Template.slug == slug)) is None:
                session.add(Template(slug=slug, title=title, body=body))

        defaults = {
            "timezone": {"value": self.settings.timezone},
            "morning_time": {"value": self.settings.morning_time.isoformat()},
            "evening_time": {"value": self.settings.evening_time.isoformat()},
            "weekly_review_time": {"value": self.settings.weekly_review_time.isoformat()},
            "purchase_confirmation_threshold": {
                "value": str(self.settings.purchase_confirmation_threshold)
            },
            "summary_mode": {"value": self.settings.summary_mode.value},
            "archive_retention_days": {"value": self.settings.archive_retention_days},
        }
        for key, value in defaults.items():
            if session.scalar(select(SystemSetting).where(SystemSetting.key == key)) is None:
                session.add(SystemSetting(key=key, value_json=value))
        bind = session.get_bind()
        self._upsert_health(session, "database", HealthStatus.OK, {"dialect": bind.dialect.name})
        session.commit()

    def create_purchase(self, session: Session, form: PurchaseCreateForm, created_by: str) -> Purchase:
        confirmation_required = purchase_requires_confirmation(
            amount=form.budget_amount,
            threshold=self.settings.purchase_confirmation_threshold,
            category=form.category,
        )
        purchase = Purchase(
            created_by=created_by,
            category=form.category,
            title=form.title,
            description=form.description,
            budget_amount=form.budget_amount,
            currency=form.currency,
            payer_mode=form.payer_mode,
            driver_user_id=form.driver_user_id,
            approver_user_id=form.approver_user_id,
            confirmation_required=confirmation_required,
            deadline_at=form.deadline_at,
            notes=form.notes,
            status=(
                PurchaseStatus.WAITING_CONFIRMATION
                if confirmation_required
                else PurchaseStatus.APPROVED
            ),
        )
        session.add(purchase)
        self._audit(session, "purchase.created", {"purchase_id": purchase.id, "title": purchase.title})
        session.commit()
        session.refresh(purchase)
        return purchase

    def create_chore(self, session: Session, form: ChoreCreateForm) -> Chore:
        history = [
            BalanceSnapshot(user_id=item[0], load_score=item[1])
            for item in session.execute(
                select(Chore.assigned_user_id, func.count(Chore.id))
                .where(Chore.chore_type == form.chore_type, Chore.assigned_user_id.is_not(None))
                .group_by(Chore.assigned_user_id)
            )
            if item[0] is not None
        ]
        assigned = choose_chore_assignee(
            mode=form.mode,
            automation_mode=AutomationMode.BALANCE,
            primary_user_id=form.assigned_user_id,
            secondary_user_id=form.backup_user_id,
            history=history,
        )
        chore = Chore(
            title=form.title,
            chore_type=form.chore_type,
            frequency=form.frequency,
            mode=form.mode,
            due_at=form.due_at,
            assigned_user_id=assigned,
            backup_user_id=form.backup_user_id,
            estimated_minutes=form.estimated_minutes,
            notes=form.notes,
            status=ChoreStatus.TODO,
        )
        session.add(chore)
        self._audit(session, "chore.created", {"chore_id": chore.id, "title": chore.title})
        session.commit()
        session.refresh(chore)
        return chore

    def create_decision(self, session: Session, form: DecisionCreateForm) -> Decision:
        status = (
            DecisionStatus.WAITING_CONFIRMATION
            if form.approver_user_id
            else DecisionStatus.PROPOSED
        )
        decision = Decision(
            question=form.question,
            options_json=form.options,
            driver_user_id=form.driver_user_id,
            approver_user_id=form.approver_user_id,
            deadline_at=form.deadline_at,
            rationale_short=form.rationale_short,
            status=status,
        )
        session.add(decision)
        self._audit(session, "decision.created", {"decision_id": decision.id})
        session.commit()
        session.refresh(decision)
        return decision

    def create_note(self, session: Session, form: NoteCreateForm) -> Note:
        category = self.ai_client.classify(form.text)
        note = Note(text=form.text, created_by=form.created_by, category_guess=category.value)
        session.add(note)
        self._audit(session, "note.created", {"note_id": note.id, "category_guess": category.value})
        session.commit()
        session.refresh(note)
        return note

    def create_event(self, session: Session, form: EventCreateForm) -> Event:
        event = Event(
            owner_user_id=form.owner_user_id,
            title=form.title,
            category=form.category,
            date=form.date,
            start_at=form.start_at,
            end_at=form.end_at,
            location=form.location,
            is_joint=form.is_joint,
            notes=form.notes,
            source=form.source,
            status=EventStatus.PLANNED,
        )
        session.add(event)
        self._audit(session, "event.created", {"event_id": event.id, "title": event.title})
        session.commit()
        session.refresh(event)
        return event

    def upsert_daily_plan(self, session: Session, form: DailyPlanForm) -> DailyPlan:
        plan = session.scalar(
            select(DailyPlan).where(DailyPlan.user_id == form.user_id, DailyPlan.date == form.date)
        )
        if plan is None:
            plan = DailyPlan(user_id=form.user_id, date=form.date)
            session.add(plan)
        plan.location = form.location
        plan.busy_from = form.busy_from
        plan.busy_to = form.busy_to
        plan.after_work = form.after_work
        plan.important_today = form.important_today
        plan.joint_plan = form.joint_plan
        plan.shopping_today = form.shopping_today
        plan.household_evening = form.household_evening
        self._audit(session, "daily_plan.upserted", {"user_id": form.user_id, "date": str(form.date)})
        session.commit()
        session.refresh(plan)
        return plan

    def upsert_weekly_plan(self, session: Session, form: WeeklyPlanForm) -> WeeklyPlan:
        plan = session.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == form.week_start))
        if plan is None:
            plan = WeeklyPlan(week_start=form.week_start)
            session.add(plan)
        plan.summary = form.summary
        plan.goals_json = form.goals
        plan.joint_plans_json = form.joint_plans
        self._audit(session, "weekly_plan.upserted", {"week_start": str(form.week_start)})
        session.commit()
        session.refresh(plan)
        return plan

    def update_system_settings(self, session: Session, form: SettingsUpdateForm) -> list[SystemSetting]:
        items: list[SystemSetting] = []
        for key, value in form.values.items():
            setting = session.scalar(select(SystemSetting).where(SystemSetting.key == key))
            if setting is None:
                setting = SystemSetting(key=key, value_json={"value": value})
                session.add(setting)
            else:
                setting.value_json = {"value": value}
            items.append(setting)
        self._audit(session, "settings.updated", {"keys": list(form.values)})
        session.commit()
        return items

    def dashboard(self, session: Session) -> DashboardView:
        today = datetime.now(tz=UTC).date()
        week_start = today - timedelta(days=today.weekday())
        weekly = session.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == week_start))
        return DashboardView(
            today_events=[self._event_card(item) for item in session.scalars(select(Event).where(Event.date == today)).all()],
            pending_purchases=[
                self._purchase_card(item)
                for item in session.scalars(
                    select(Purchase).where(
                        Purchase.status.in_(
                            [
                                PurchaseStatus.IDEA,
                                PurchaseStatus.WAITING_CONFIRMATION,
                                PurchaseStatus.APPROVED,
                            ]
                        )
                    )
                ).all()
            ],
            chores_today=[
                self._chore_card(item)
                for item in session.scalars(
                    select(Chore).where(
                        or_(Chore.due_at.is_(None), func.date(Chore.due_at) <= today),
                        Chore.status.in_([ChoreStatus.TODO, ChoreStatus.IN_PROGRESS, ChoreStatus.MOVED]),
                    )
                ).all()
            ],
            pending_decisions=[
                self._decision_card(item)
                for item in session.scalars(
                    select(Decision).where(
                        Decision.status.in_(
                            [DecisionStatus.PROPOSED, DecisionStatus.WAITING_CONFIRMATION]
                        )
                    )
                ).all()
            ],
            notes_inbox=[
                {"id": item.id, "text": item.text, "suggestion": item.category_guess or "unknown"}
                for item in session.scalars(select(Note).where(Note.status == NoteStatus.OPEN)).all()
            ],
            weekly_goals=weekly.goals_json if weekly is not None else [],
            health=[
                {
                    "component": item.component,
                    "status": item.status,
                    "details": item.details_json,
                }
                for item in session.scalars(select(SystemHealth)).all()
            ],
        )

    def search(self, session: Session, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        results: list[SearchResult] = []
        results.extend(self._search_model(session, Purchase, query, "title", "description"))
        results.extend(self._search_model(session, Decision, query, "question", "rationale_short"))
        results.extend(self._search_model(session, Note, query, "text", "category_guess"))
        results.extend(self._search_model(session, Chore, query, "title", "notes"))
        results.extend(self._search_model(session, Event, query, "title", "notes"))
        return results

    def export_bundle(self, session: Session) -> ExportBundle:
        payload = {
            "users": [self._row_dict(item) for item in session.scalars(select(User)).all()],
            "chats": [self._row_dict(item) for item in session.scalars(select(Chat)).all()],
            "topics": [self._row_dict(item) for item in session.scalars(select(Topic)).all()],
            "daily_plans": [self._row_dict(item) for item in session.scalars(select(DailyPlan)).all()],
            "weekly_plans": [self._row_dict(item) for item in session.scalars(select(WeeklyPlan)).all()],
            "events": [self._row_dict(item) for item in session.scalars(select(Event)).all()],
            "purchases": [self._row_dict(item) for item in session.scalars(select(Purchase)).all()],
            "chores": [self._row_dict(item) for item in session.scalars(select(Chore)).all()],
            "decisions": [self._row_dict(item) for item in session.scalars(select(Decision)).all()],
            "notes": [self._row_dict(item) for item in session.scalars(select(Note)).all()],
            "reminders": [self._row_dict(item) for item in session.scalars(select(Reminder)).all()],
            "templates": [self._row_dict(item) for item in session.scalars(select(Template)).all()],
            "system_settings": [
                self._row_dict(item) for item in session.scalars(select(SystemSetting)).all()
            ],
            "user_settings": [
                self._row_dict(item) for item in session.scalars(select(UserSetting)).all()
            ],
            "system_health": [
                self._row_dict(item) for item in session.scalars(select(SystemHealth)).all()
            ],
            "message_links": [
                self._row_dict(item) for item in session.scalars(select(MessageLink)).all()
            ],
            "automation_rules": [
                self._row_dict(item) for item in session.scalars(select(AutomationRule)).all()
            ],
            "audit_log": [self._row_dict(item) for item in session.scalars(select(AuditLog)).all()],
        }
        markdown = self._export_markdown(payload)
        return ExportBundle(payload=payload, markdown=markdown)

    def create_backup(self, session: Session) -> Path:
        bundle = self.export_bundle(session)
        self.settings.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        archive_path = self.settings.backup_dir / f"homegroup_backup_{stamp}.zip"
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zip_file:
            zip_file.writestr(
                "snapshot.json",
                json.dumps(bundle.payload, ensure_ascii=False, default=str, indent=2),
            )
            zip_file.writestr("snapshot.md", bundle.markdown)
            zip_file.writestr(
                "meta.json",
                json.dumps(
                    {
                        "created_at": datetime.now(tz=UTC).isoformat(),
                        "app_name": self.settings.app_name,
                        "env": self.settings.env,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        self._upsert_health(session, "backup", HealthStatus.OK, {"last_backup": archive_path.name})
        session.commit()
        return archive_path

    def restore_backup(self, session: Session, archive_path: Path) -> None:
        with ZipFile(archive_path, "r") as zip_file:
            payload = json.loads(zip_file.read("snapshot.json").decode("utf-8"))
        self._replace_rows(session, payload)
        self._upsert_health(session, "backup_restore", HealthStatus.OK, {"restored_from": archive_path.name})
        session.commit()

    def diagnostics(self, session: Session) -> dict[str, object]:
        self.ensure_defaults(session)
        counts = {
            "users": session.scalar(select(func.count(User.id))) or 0,
            "events": session.scalar(select(func.count(Event.id))) or 0,
            "purchases": session.scalar(select(func.count(Purchase.id))) or 0,
            "chores": session.scalar(select(func.count(Chore.id))) or 0,
            "decisions": session.scalar(select(func.count(Decision.id))) or 0,
            "notes": session.scalar(select(func.count(Note.id))) or 0,
        }
        components = [
            {"component": item.component, "status": item.status, "details": item.details_json}
            for item in session.scalars(select(SystemHealth)).all()
        ]
        return {"counts": counts, "components": components, "webhook_url": self.settings.webhook_url}

    def generate_summary(self, session: Session, kind: str) -> str:
        dashboard = self.dashboard(session)
        lines = [
            f"События сегодня: {len(dashboard.today_events)}",
            f"Покупки в работе: {len(dashboard.pending_purchases)}",
            f"Бытовые задачи: {len(dashboard.chores_today)}",
            f"Решения ждут подтверждения: {len(dashboard.pending_decisions)}",
            f"Заметки во входящих: {len(dashboard.notes_inbox)}",
        ]
        return self.ai_client.summarize(kind, lines)

    def note_conversion_suggestion(self, text_value: str) -> tuple[str, str] | None:
        return self.ai_client.suggest_note_conversion(text_value)

    def classify_message(self, text_value: str) -> AIClassification:
        return self.ai_client.classify(text_value)

    def _replace_rows(self, session: Session, payload: dict[str, list[dict[str, object]]]) -> None:
        model_order: list[tuple[str, type[Base]]] = [
            ("message_links", MessageLink),
            ("reminders", Reminder),
            ("notes", Note),
            ("decisions", Decision),
            ("chores", Chore),
            ("purchases", Purchase),
            ("events", Event),
            ("daily_plans", DailyPlan),
            ("topics", Topic),
            ("chats", Chat),
            ("user_settings", UserSetting),
            ("system_settings", SystemSetting),
            ("weekly_plans", WeeklyPlan),
            ("templates", Template),
            ("system_health", SystemHealth),
            ("automation_rules", AutomationRule),
            ("audit_log", AuditLog),
            ("users", User),
        ]
        for _, model in model_order:
            session.execute(text(f"DELETE FROM {model.__tablename__}"))
        session.flush()
        session.expunge_all()

        restore_order = list(reversed(model_order))
        for key, model in restore_order:
            for row in payload.get(key, []):
                session.add(model(**self._deserialize_row(model, row)))

    def _search_model(
        self,
        session: Session,
        model: type[Base],
        query: str,
        title_column: str,
        subtitle_column: str,
    ) -> list[SearchResult]:
        title_attr = getattr(model, title_column)
        subtitle_attr = getattr(model, subtitle_column)
        rows = session.scalars(
            select(model).where(
                or_(
                    cast(title_attr, String).ilike(f"%{query}%"),
                    cast(subtitle_attr, String).ilike(f"%{query}%"),
                )
            )
        ).all()
        return [
            SearchResult(
                entity_type=model.__tablename__,
                entity_id=str(getattr(item, "id")),
                title=str(getattr(item, title_column)),
                subtitle=str(getattr(item, subtitle_column) or ""),
            )
            for item in rows
        ]

    def _upsert_health(
        self,
        session: Session,
        component: str,
        status: HealthStatus,
        details: dict[str, object],
    ) -> None:
        entry = session.scalar(select(SystemHealth).where(SystemHealth.component == component))
        if entry is None:
            entry = SystemHealth(
                component=component,
                status=status,
                last_checked_at=datetime.now(tz=UTC),
                details_json=details,
            )
            session.add(entry)
        else:
            entry.status = status
            entry.last_checked_at = datetime.now(tz=UTC)
            entry.details_json = details

    def _audit(self, session: Session, action: str, payload: dict[str, object]) -> None:
        session.add(
            AuditLog(
                actor_type="SYSTEM",
                action=action,
                payload_json=payload,
                created_at=datetime.now(tz=UTC),
            )
        )

    def _purchase_card(self, item: Purchase) -> dict[str, object]:
        return {
            "id": item.id,
            "title": item.title,
            "status": item.status,
            "budget": f"{item.budget_amount or 0} {item.currency}",
            "needs_confirmation": item.confirmation_required,
        }

    def _chore_card(self, item: Chore) -> dict[str, object]:
        return {
            "id": item.id,
            "title": item.title,
            "status": item.status,
            "due_at": item.due_at.isoformat() if item.due_at else "",
        }

    def _decision_card(self, item: Decision) -> dict[str, object]:
        return {
            "id": item.id,
            "question": item.question,
            "status": item.status,
            "deadline_at": item.deadline_at.isoformat() if item.deadline_at else "",
        }

    def _event_card(self, item: Event) -> dict[str, object]:
        return {
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "location": item.location or "",
            "date": item.date.isoformat(),
        }

    def _row_dict(self, item: object) -> dict[str, object]:
        return {
            column.name: self._serialize_value(getattr(item, column.name))
            for column in item.__table__.columns  # type: ignore[attr-defined]
        }

    def _serialize_value(self, value: object) -> object:
        if isinstance(value, datetime | date | time):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if hasattr(value, "value"):
            return getattr(value, "value")
        return value

    def _deserialize_row(self, model: type[Base], row: dict[str, object]) -> dict[str, object]:
        values: dict[str, object] = {}
        for column in model.__table__.columns:
            raw_value = row.get(column.name)
            if raw_value is None:
                values[column.name] = None
                continue
            if isinstance(column.type, SADateTime):
                values[column.name] = datetime.fromisoformat(str(raw_value))
            elif isinstance(column.type, SADate):
                values[column.name] = date.fromisoformat(str(raw_value))
            elif isinstance(column.type, SATime):
                values[column.name] = time.fromisoformat(str(raw_value))
            elif isinstance(column.type, SANumeric):
                values[column.name] = Decimal(str(raw_value))
            elif isinstance(column.type, SABoolean):
                values[column.name] = bool(raw_value)
            elif isinstance(column.type, SAJSON):
                values[column.name] = raw_value
            else:
                values[column.name] = raw_value
        return values

    def _export_markdown(self, payload: dict[str, list[dict[str, object]]]) -> str:
        lines = ["# HomeGroup Export", ""]
        for key, rows in payload.items():
            lines.append(f"## {key}")
            if not rows:
                lines.append("_empty_")
                lines.append("")
                continue
            for row in rows:
                title = row.get("title") or row.get("question") or row.get("text") or row.get("id")
                lines.append(f"- **{title}**")
                for name, value in row.items():
                    if name == "id":
                        continue
                    lines.append(f"  - {name}: {value}")
            lines.append("")
        return "\n".join(lines)


def build_service(settings: Settings, ai_client_factory: Callable[[], AIClient]) -> HomeGroupService:
    return HomeGroupService(settings=settings, ai_client=ai_client_factory())
