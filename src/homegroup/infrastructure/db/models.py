from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import String as SAString
from sqlalchemy.orm import Mapped, mapped_column, relationship

from homegroup.domain.enums import (
    ChoreFrequency,
    ChoreMode,
    ChoreStatus,
    ChoreType,
    DecisionStatus,
    EntityType,
    EventCategory,
    EventStatus,
    HealthStatus,
    NoteStatus,
    PayerMode,
    PurchaseCategory,
    PurchaseStatus,
    ReminderKind,
    UserRole,
)
from homegroup.infrastructure.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str | None] = mapped_column(SAString(255))
    display_name: Mapped[str] = mapped_column(SAString(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAString(32), nullable=False)
    timezone: Mapped[str] = mapped_column(SAString(64), default="Europe/Moscow", nullable=False)
    language: Mapped[str] = mapped_column(SAString(8), default="ru", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Chat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chats"

    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    chat_type: Mapped[str] = mapped_column(SAString(32), nullable=False)
    is_forum: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    title: Mapped[str] = mapped_column(SAString(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())

    topics: Mapped[list[Topic]] = relationship(back_populates="chat")


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("chat_id", "slug"),)

    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id"), nullable=False)
    slug: Mapped[str] = mapped_column(SAString(64), nullable=False)
    title: Mapped[str] = mapped_column(SAString(255), nullable=False)
    telegram_message_thread_id: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(SAString(64), default="generic", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message_policy: Mapped[str] = mapped_column(SAString(64), default="default", nullable=False)
    autopost_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    chat: Mapped[Chat] = relationship(back_populates="topics")


class DailyPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(SAString(255))
    busy_from: Mapped[time | None] = mapped_column(Time(timezone=False))
    busy_to: Mapped[time | None] = mapped_column(Time(timezone=False))
    after_work: Mapped[str | None] = mapped_column(Text())
    important_today: Mapped[str | None] = mapped_column(Text())
    joint_plan: Mapped[str | None] = mapped_column(Text())
    shopping_today: Mapped[str | None] = mapped_column(Text())
    household_evening: Mapped[str | None] = mapped_column(Text())


class WeeklyPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (UniqueConstraint("week_start"),)

    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text())
    goals_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    joint_plans_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "events"

    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(SAString(255), nullable=False)
    category: Mapped[EventCategory] = mapped_column(SAString(32), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(SAString(255))
    is_joint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        SAString(32),
        default=EventStatus.PLANNED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text())
    source: Mapped[str] = mapped_column(SAString(64), default="manual", nullable=False)
    posted_message_id: Mapped[int | None] = mapped_column(BigInteger)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))


class Purchase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchases"

    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[PurchaseCategory] = mapped_column(SAString(32), nullable=False)
    title: Mapped[str] = mapped_column(SAString(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    priority: Mapped[str] = mapped_column(SAString(32), default="normal", nullable=False)
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(SAString(8), default="RUB", nullable=False)
    payer_mode: Mapped[PayerMode] = mapped_column(
        SAString(32),
        default=PayerMode.SEPARATE_NO_SPLIT,
        nullable=False,
    )
    driver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[PurchaseStatus] = mapped_column(
        SAString(32),
        default=PurchaseStatus.IDEA,
        nullable=False,
    )
    links_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text())
    posted_message_id: Mapped[int | None] = mapped_column(BigInteger)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))


class Chore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chores"

    title: Mapped[str] = mapped_column(SAString(255), nullable=False)
    chore_type: Mapped[ChoreType] = mapped_column(SAString(32), nullable=False)
    frequency: Mapped[ChoreFrequency] = mapped_column(
        SAString(32),
        default=ChoreFrequency.ONCE,
        nullable=False,
    )
    mode: Mapped[ChoreMode] = mapped_column(SAString(32), nullable=False)
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    backup_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(SAString(32), default="normal", nullable=False)
    status: Mapped[ChoreStatus] = mapped_column(
        SAString(32),
        default=ChoreStatus.TODO,
        nullable=False,
    )
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text())
    posted_message_id: Mapped[int | None] = mapped_column(BigInteger)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))


class Decision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "decisions"

    question: Mapped[str] = mapped_column(Text(), nullable=False)
    options_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    driver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[DecisionStatus] = mapped_column(
        SAString(32),
        default=DecisionStatus.PROPOSED,
        nullable=False,
    )
    final_decision: Mapped[str | None] = mapped_column(Text())
    rationale_short: Mapped[str | None] = mapped_column(Text())
    posted_message_id: Mapped[int | None] = mapped_column(BigInteger)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))


class Note(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notes"

    text: Mapped[str] = mapped_column(Text(), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_guess: Mapped[str | None] = mapped_column(SAString(64))
    converted_to_entity_type: Mapped[EntityType | None] = mapped_column(SAString(32))
    converted_to_entity_id: Mapped[str | None] = mapped_column(SAString(36))
    status: Mapped[NoteStatus] = mapped_column(
        SAString(32),
        default=NoteStatus.OPEN,
        nullable=False,
    )


class Reminder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reminders"

    kind: Mapped[ReminderKind] = mapped_column(SAString(32), nullable=False)
    target_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    target_chat_id: Mapped[str | None] = mapped_column(ForeignKey("chats.id"))
    target_topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    cron_expr: Mapped[str] = mapped_column(SAString(128), nullable=False)
    timezone: Mapped[str] = mapped_column(SAString(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_hours_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class MessageLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_links"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id"),
        UniqueConstraint("telegram_chat_id", "telegram_message_id"),
    )

    entity_type: Mapped[EntityType] = mapped_column(SAString(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(SAString(36), nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_thread_id: Mapped[int | None] = mapped_column(BigInteger)


class Template(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "templates"

    slug: Mapped[str] = mapped_column(SAString(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(SAString(255), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AutomationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_rules"

    name: Mapped[str] = mapped_column(SAString(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(SAString(64), nullable=False)
    conditions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    actions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_log"

    actor_type: Mapped[str] = mapped_column(SAString(64), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(SAString(64))
    action: Mapped[str] = mapped_column(SAString(128), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SystemHealth(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "system_health"

    component: Mapped[str] = mapped_column(SAString(64), unique=True, nullable=False)
    status: Mapped[HealthStatus] = mapped_column(SAString(32), nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


Index("ix_topics_chat_slug", Topic.chat_id, Topic.slug)
Index("ix_message_links_entity", MessageLink.entity_type, MessageLink.entity_id)
Index("ix_events_date", Event.date)
Index("ix_purchases_status", Purchase.status)
Index("ix_chores_status_due_at", Chore.status, Chore.due_at)
Index("ix_decisions_status_deadline", Decision.status, Decision.deadline_at)
