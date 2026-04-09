from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from homegroup.domain.enums import (
    AutomationMode,
    ChoreMode,
    PurchaseCategory,
    PurchaseStatus,
)
from homegroup.domain.rules import (
    BalanceSnapshot,
    choose_chore_assignee,
    decision_is_expired,
    next_purchase_status_after_confirmation,
    purchase_requires_confirmation,
    should_archive,
)


def test_big_purchase_always_requires_confirmation() -> None:
    assert purchase_requires_confirmation(
        amount=Decimal("1"),
        threshold=Decimal("15000"),
        category=PurchaseCategory.BIG_PURCHASE,
    )


def test_regular_purchase_threshold_is_respected() -> None:
    assert not purchase_requires_confirmation(
        amount=Decimal("14999"),
        threshold=Decimal("15000"),
        category=PurchaseCategory.HOUSEHOLD,
    )
    assert purchase_requires_confirmation(
        amount=Decimal("15000"),
        threshold=Decimal("15000"),
        category=PurchaseCategory.HOUSEHOLD,
    )


def test_confirmation_status_transition() -> None:
    assert next_purchase_status_after_confirmation(True) is PurchaseStatus.APPROVED
    assert next_purchase_status_after_confirmation(False) is PurchaseStatus.POSTPONED


def test_rotation_assignment_switches_between_users() -> None:
    assignee = choose_chore_assignee(
        mode=ChoreMode.ALTERNATING,
        automation_mode=AutomationMode.ROTATION,
        primary_user_id="a",
        secondary_user_id="b",
        history=[BalanceSnapshot(user_id="a", load_score=2)],
    )

    assert assignee == "b"


def test_balance_assignment_picks_lowest_load() -> None:
    assignee = choose_chore_assignee(
        mode=ChoreMode.ALTERNATING,
        automation_mode=AutomationMode.BALANCE,
        primary_user_id="a",
        secondary_user_id="b",
        history=[
            BalanceSnapshot(user_id="a", load_score=5),
            BalanceSnapshot(user_id="b", load_score=2),
        ],
    )

    assert assignee == "b"


def test_archive_policy_respects_done_state() -> None:
    old = datetime.now(tz=UTC) - timedelta(days=200)
    assert should_archive(updated_at=old, retention_days=180, is_done=True)
    assert not should_archive(updated_at=old, retention_days=180, is_done=False)


def test_decision_expiry_is_deadline_driven() -> None:
    past = datetime.now(tz=UTC) - timedelta(minutes=1)
    future = datetime.now(tz=UTC) + timedelta(minutes=1)
    assert decision_is_expired(past)
    assert not decision_is_expired(future)
    assert not decision_is_expired(None)
