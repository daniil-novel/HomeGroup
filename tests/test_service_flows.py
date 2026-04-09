from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from homegroup.application.schemas import NoteCreateForm, PurchaseCreateForm
from homegroup.application.services import HomeGroupService
from homegroup.domain.enums import PayerMode, PurchaseCategory, PurchaseStatus, UserRole
from homegroup.infrastructure.ai import FallbackAIClient
from homegroup.infrastructure.config import Settings
from homegroup.infrastructure.db.base import Base
from homegroup.infrastructure.db.models import Purchase, User


def build_service(tmp_path: Path) -> tuple[HomeGroupService, sessionmaker[Session]]:
    db_path = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{db_path}",
        backup_dir=tmp_path / "backups",
        bot_token="test-token",
    )
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    service = HomeGroupService(settings=settings, ai_client=FallbackAIClient())
    return service, session_factory


def create_user(session: Session, telegram_user_id: int, name: str) -> User:
    user = User(
        telegram_user_id=telegram_user_id,
        display_name=name,
        username=name.lower(),
        role=UserRole.OWNER_A,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_purchase_flow_sets_confirmation_threshold(tmp_path: Path) -> None:
    service, session_factory = build_service(tmp_path)
    with session_factory() as session:
        user = create_user(session, 1, "Daniil")
        purchase = service.create_purchase(
            session,
            PurchaseCreateForm(
                title="Пылесос",
                category=PurchaseCategory.BIG_PURCHASE,
                budget_amount=Decimal("25000"),
                payer_mode=PayerMode.PAYER_A,
            ),
            created_by=user.id,
        )

        assert purchase.status == PurchaseStatus.WAITING_CONFIRMATION
        assert purchase.confirmation_required


def test_dashboard_and_search_include_created_note(tmp_path: Path) -> None:
    service, session_factory = build_service(tmp_path)
    with session_factory() as session:
        user = create_user(session, 1, "Daniil")
        service.ensure_defaults(session)
        service.create_note(
            session,
            NoteCreateForm(created_by=user.id, text="Надо купить порошок для стирки"),
        )

        dashboard = service.dashboard(session)
        search = service.search(session, "порошок")

        assert len(dashboard.notes_inbox) == 1
        assert search


def test_backup_restore_roundtrip(tmp_path: Path) -> None:
    service, session_factory = build_service(tmp_path)
    with session_factory() as session:
        user = create_user(session, 1, "Daniil")
        service.create_purchase(
            session,
            PurchaseCreateForm(
                title="Фильтр для воды",
                category=PurchaseCategory.HOUSEHOLD,
                budget_amount=Decimal("1200"),
                payer_mode=PayerMode.PAYER_A,
            ),
            created_by=user.id,
        )
        archive = service.create_backup(session)

        session.execute(delete(Purchase))
        session.commit()
        assert session.scalar(select(Purchase)) is None

        service.restore_backup(session, archive)
        restored = session.scalar(select(Purchase))

        assert restored is not None
        assert restored.title == "Фильтр для воды"


def test_summary_uses_fallback_ai(tmp_path: Path) -> None:
    service, session_factory = build_service(tmp_path)
    with session_factory() as session:
        summary = service.generate_summary(session, "Утро")

    assert "Утро" in summary
