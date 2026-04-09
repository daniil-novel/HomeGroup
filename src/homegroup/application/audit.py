from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from homegroup.infrastructure.db.models import AuditLog


@dataclass(slots=True)
class AuditEntry:
    actor_type: str
    action: str
    actor_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_model(self) -> AuditLog:
        return AuditLog(
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            action=self.action,
            payload_json=self.payload,
            created_at=datetime.now(tz=UTC),
        )

