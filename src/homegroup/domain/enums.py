from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    OWNER_A = "OWNER_A"
    OWNER_B = "OWNER_B"
    BOT = "BOT"
    SYSTEM_AGENT = "SYSTEM_AGENT"


class PayerMode(StrEnum):
    PAYER_A = "payer_a"
    PAYER_B = "payer_b"
    SPLIT_EQUAL = "split_equal"
    SPLIT_CUSTOM = "split_custom"
    SEPARATE_NO_SPLIT = "separate_no_split"


class TopicSlug(StrEnum):
    TODAY = "today"
    WEEK = "week"
    CALENDAR = "calendar"
    PURCHASES = "purchases"
    CHORES = "chores"
    DECISIONS = "decisions"
    NOTES = "notes"
    TEMPLATES = "templates"
    ARCHIVE = "archive"
    SYSTEM = "system"


class PurchaseCategory(StrEnum):
    GROCERY = "grocery"
    HOUSEHOLD = "household"
    BIG_PURCHASE = "big_purchase"
    LATER = "later"
    PERSONAL_A = "personal_a"
    PERSONAL_B = "personal_b"
    GIFT = "gift"
    SUBSCRIPTION = "subscription"
    REPAIR = "repair"


class PurchaseStatus(StrEnum):
    IDEA = "idea"
    COMPARE = "compare"
    WAITING_CONFIRMATION = "waiting_confirmation"
    APPROVED = "approved"
    BOUGHT = "bought"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ChoreType(StrEnum):
    CLEANING = "cleaning"
    LAUNDRY = "laundry"
    KITCHEN = "kitchen"
    DISHES = "dishes"
    TRASH = "trash"
    GROCERIES = "groceries"
    BEDDING = "bedding"
    BATHROOM = "bathroom"
    BILLS = "bills"
    COOKING = "cooking"
    SUPPLIES = "supplies"


class ChoreMode(StrEnum):
    TOGETHER = "together"
    ALTERNATING = "alternating"
    WHO_IS_FREE = "who_is_free"
    FIXED_ASSIGNEE = "fixed_assignee"


class AutomationMode(StrEnum):
    ROTATION = "rotation"
    BALANCE = "balance"
    MANUAL = "manual"
    WHO_IS_FREE = "who_is_free"


class ChoreStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    MOVED = "moved"
    SKIPPED = "skipped"
    ARCHIVED = "archived"


class ChoreFrequency(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    EVERY_2_DAYS = "every_2_days"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM_RRULE = "custom_rrule"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class EventCategory(StrEnum):
    WORK = "work"
    STUDY = "study"
    GYM = "gym"
    TENNIS = "tennis"
    MEETING = "meeting"
    TRIP = "trip"
    PERSONAL = "personal"
    JOINT = "joint"


class EventStatus(StrEnum):
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    DONE = "done"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class NoteStatus(StrEnum):
    OPEN = "open"
    CONVERTED = "converted"
    ARCHIVED = "archived"


class ReminderKind(StrEnum):
    MORNING = "morning"
    EVENING = "evening"
    WEEKLY_REVIEW = "weekly_review"
    DEADLINE = "deadline"
    RECURRING = "recurring"
    PERSONAL = "personal"


class EntityType(StrEnum):
    DAILY_PLAN = "daily_plan"
    WEEKLY_PLAN = "weekly_plan"
    EVENT = "event"
    PURCHASE = "purchase"
    CHORE = "chore"
    DECISION = "decision"
    NOTE = "note"
    SUMMARY = "summary"
    TEMPLATE = "template"


class AIClassification(StrEnum):
    TODAY_PLAN = "today_plan"
    WEEK_PLAN = "week_plan"
    CALENDAR_EVENT = "calendar_event"
    PURCHASE = "purchase"
    CHORE = "chore"
    DECISION = "decision"
    NOTE = "note"
    REMINDER_REQUEST = "reminder_request"
    STATUS_UPDATE = "status_update"
    UNKNOWN = "unknown"


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class SummaryMode(StrEnum):
    COMPACT = "compact"
    STANDARD = "standard"
    EXTENDED = "extended"

