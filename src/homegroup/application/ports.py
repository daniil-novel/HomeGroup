from __future__ import annotations

from typing import Protocol

from homegroup.domain.enums import AIClassification


class AIClient(Protocol):
    def classify(self, text: str) -> AIClassification: ...

    def extract(self, text: str) -> dict[str, str | bool | None]: ...

    def summarize(self, title: str, lines: list[str]) -> str: ...

    def suggest_note_conversion(self, text: str) -> tuple[str, str] | None: ...


class TelegramGateway(Protocol):
    def publish_summary(self, topic_slug: str, text: str) -> None: ...

    def publish_system_message(self, text: str) -> None: ...

    def upsert_entity_card(self, entity_type: str, entity_id: str, body: str, topic_slug: str) -> None: ...


class ProvisioningGateway(Protocol):
    def provision(self) -> str: ...

