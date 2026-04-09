from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from homegroup.domain.enums import (
    AutomationMode,
    ChoreMode,
    PurchaseCategory,
    PurchaseStatus,
)


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def purchase_requires_confirmation(
    amount: Decimal | None,
    threshold: Decimal,
    category: PurchaseCategory,
) -> bool:
    if category is PurchaseCategory.BIG_PURCHASE:
        return True
    if amount is None:
        return False
    return amount >= threshold


def next_purchase_status_after_confirmation(approved: bool) -> PurchaseStatus:
    return PurchaseStatus.APPROVED if approved else PurchaseStatus.POSTPONED


def next_due_at(last_completed_at: datetime, frequency_days: int) -> datetime:
    return last_completed_at + timedelta(days=frequency_days)


@dataclass(slots=True)
class BalanceSnapshot:
    user_id: str
    load_score: int


def choose_chore_assignee(
    mode: ChoreMode,
    automation_mode: AutomationMode,
    primary_user_id: str | None,
    secondary_user_id: str | None,
    history: Sequence[BalanceSnapshot],
) -> str | None:
    if mode is ChoreMode.FIXED_ASSIGNEE:
        return primary_user_id
    if mode is ChoreMode.TOGETHER:
        return None
    if automation_mode is AutomationMode.MANUAL:
        return primary_user_id
    if automation_mode is AutomationMode.WHO_IS_FREE or mode is ChoreMode.WHO_IS_FREE:
        return None
    if automation_mode is AutomationMode.BALANCE:
        if not history:
            return primary_user_id
        ranked = sorted(history, key=lambda item: item.load_score)
        return ranked[0].user_id
    if automation_mode is AutomationMode.ROTATION or mode is ChoreMode.ALTERNATING:
        if history:
            last_owner = history[-1].user_id
            if last_owner == primary_user_id:
                return secondary_user_id
        return primary_user_id
    return primary_user_id


def should_archive(updated_at: datetime, retention_days: int, is_done: bool) -> bool:
    if not is_done:
        return False
    return utcnow() - updated_at >= timedelta(days=retention_days)


def decision_is_expired(deadline_at: datetime | None) -> bool:
    if deadline_at is None:
        return False
    return deadline_at <= utcnow()
