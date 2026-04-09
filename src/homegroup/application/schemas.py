from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from homegroup.domain.enums import ChoreFrequency, ChoreMode, ChoreType, PayerMode, PurchaseCategory


class PurchaseCreateForm(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: PurchaseCategory
    description: str | None = None
    budget_amount: Decimal | None = None
    currency: str = "RUB"
    payer_mode: PayerMode = PayerMode.SEPARATE_NO_SPLIT
    driver_user_id: str | None = None
    approver_user_id: str | None = None
    deadline_at: datetime | None = None
    notes: str | None = None


class ChoreCreateForm(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    chore_type: ChoreType
    frequency: ChoreFrequency = ChoreFrequency.ONCE
    mode: ChoreMode
    due_at: datetime | None = None
    assigned_user_id: str | None = None
    backup_user_id: str | None = None
    estimated_minutes: int | None = None
    notes: str | None = None


class DecisionCreateForm(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    driver_user_id: str | None = None
    approver_user_id: str | None = None
    deadline_at: datetime | None = None
    rationale_short: str | None = None


class NoteCreateForm(BaseModel):
    text: str = Field(min_length=1)
    created_by: str


class EventCreateForm(BaseModel):
    owner_user_id: str
    title: str = Field(min_length=1, max_length=255)
    category: str
    date: date
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None
    is_joint: bool = False
    notes: str | None = None
    source: str = "manual"


class DailyPlanForm(BaseModel):
    user_id: str
    date: date
    location: str | None = None
    busy_from: time | None = None
    busy_to: time | None = None
    after_work: str | None = None
    important_today: str | None = None
    joint_plan: str | None = None
    shopping_today: str | None = None
    household_evening: str | None = None


class WeeklyPlanForm(BaseModel):
    week_start: date
    summary: str | None = None
    goals: list[str] = Field(default_factory=list)
    joint_plans: list[str] = Field(default_factory=list)


class SettingsUpdateForm(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    entity_type: str
    entity_id: str
    title: str
    subtitle: str


class DashboardView(BaseModel):
    today_events: list[dict[str, Any]]
    pending_purchases: list[dict[str, Any]]
    chores_today: list[dict[str, Any]]
    pending_decisions: list[dict[str, Any]]
    notes_inbox: list[dict[str, Any]]
    weekly_goals: list[str]
    health: list[dict[str, Any]]

