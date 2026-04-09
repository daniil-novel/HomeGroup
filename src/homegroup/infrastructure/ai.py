from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from homegroup.application.ports import AIClient
from homegroup.domain.enums import AIClassification
from homegroup.infrastructure.config import Settings


@dataclass(slots=True)
class FallbackAIClient(AIClient):
    def classify(self, text: str) -> AIClassification:
        lower = text.lower()
        if any(token in lower for token in ("куп", "магаз", "закаж", "ozon", "wb")):
            return AIClassification.PURCHASE
        if any(token in lower for token in ("уборк", "стирк", "мусор", "посуд")):
            return AIClassification.CHORE
        if any(token in lower for token in ("реши", "соглас", "выбер")):
            return AIClassification.DECISION
        if re.search(r"\b\d{1,2}:\d{2}\b", lower):
            return AIClassification.CALENDAR_EVENT
        if any(token in lower for token in ("сегодня", "утро", "после работы")):
            return AIClassification.TODAY_PLAN
        if any(token in lower for token in ("недел", "выходн")):
            return AIClassification.WEEK_PLAN
        return AIClassification.NOTE

    def extract(self, text: str) -> dict[str, str | bool | None]:
        amount_match = re.search(r"(\d[\d\s]*)\s?(₽|руб|rub)?", text.lower())
        time_match = re.search(r"(\d{1,2}:\d{2})", text)
        return {
            "amount": amount_match.group(1).replace(" ", "") if amount_match else None,
            "time": time_match.group(1) if time_match else None,
            "needs_confirmation": "соглас" in text.lower(),
        }

    def summarize(self, title: str, lines: list[str]) -> str:
        return "\n".join([title, *lines[:5]])

    def suggest_note_conversion(self, text: str) -> tuple[str, str] | None:
        classification = self.classify(text)
        if classification is AIClassification.NOTE:
            return None
        mapping = {
            AIClassification.PURCHASE: ("purchase", "Похоже на покупку"),
            AIClassification.CHORE: ("chore", "Похоже на бытовую задачу"),
            AIClassification.CALENDAR_EVENT: ("event", "Похоже на событие календаря"),
            AIClassification.DECISION: ("decision", "Похоже на решение"),
            AIClassification.TODAY_PLAN: ("daily_plan", "Похоже на план дня"),
            AIClassification.WEEK_PLAN: ("weekly_plan", "Похоже на план недели"),
            AIClassification.REMINDER_REQUEST: ("reminder", "Похоже на напоминание"),
            AIClassification.STATUS_UPDATE: ("status", "Похоже на обновление статуса"),
            AIClassification.UNKNOWN: ("note", "Оставить как заметку"),
            AIClassification.NOTE: ("note", "Оставить как заметку"),
        }
        return mapping[classification]


@dataclass(slots=True)
class OpenRouterAIClient(AIClient):
    settings: Settings
    fallback: FallbackAIClient

    def classify(self, text: str) -> AIClassification:
        payload = self._complete(
            system_prompt=(
                "Classify the message into exactly one of: "
                "today_plan, week_plan, calendar_event, purchase, chore, decision, "
                "note, reminder_request, status_update, unknown."
            ),
            user_prompt=text,
        )
        try:
            return AIClassification(payload.strip().split()[0])
        except ValueError:
            return self.fallback.classify(text)

    def extract(self, text: str) -> dict[str, str | bool | None]:
        payload = self._complete(
            system_prompt=(
                "Extract a compact JSON object with keys: amount, time, date, place, "
                "needs_confirmation, priority. Use null for unknown values."
            ),
            user_prompt=text,
        )
        try:
            import json

            data = json.loads(payload)
            return {
                "amount": data.get("amount"),
                "time": data.get("time"),
                "date": data.get("date"),
                "place": data.get("place"),
                "needs_confirmation": data.get("needs_confirmation"),
                "priority": data.get("priority"),
            }
        except Exception:
            return self.fallback.extract(text)

    def summarize(self, title: str, lines: list[str]) -> str:
        payload = self._complete(
            system_prompt=(
                "Write a concise Russian summary in at most 6 short lines. "
                "Be practical and avoid corporate tone."
            ),
            user_prompt=f"{title}\n" + "\n".join(lines),
        )
        return payload.strip() or self.fallback.summarize(title, lines)

    def suggest_note_conversion(self, text: str) -> tuple[str, str] | None:
        classification = self.classify(text)
        return self.fallback.suggest_note_conversion(text) if classification else None

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.openrouter_api_key:
            return ""
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.openrouter_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except Exception:
            return ""


def build_ai_client(settings: Settings) -> AIClient:
    fallback = FallbackAIClient()
    if settings.openrouter_api_key:
        return OpenRouterAIClient(settings=settings, fallback=fallback)
    return fallback
