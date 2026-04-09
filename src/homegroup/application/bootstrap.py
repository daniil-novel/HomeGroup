from __future__ import annotations

from homegroup.domain.enums import TopicSlug

TOPIC_DEFINITIONS: list[dict[str, str | bool]] = [
    {"slug": TopicSlug.TODAY.value, "title": "Сегодня", "content_type": "planning", "is_system": False},
    {"slug": TopicSlug.WEEK.value, "title": "Неделя", "content_type": "planning", "is_system": False},
    {"slug": TopicSlug.CALENDAR.value, "title": "Календарь", "content_type": "calendar", "is_system": False},
    {"slug": TopicSlug.PURCHASES.value, "title": "Покупки", "content_type": "purchase", "is_system": False},
    {"slug": TopicSlug.CHORES.value, "title": "Быт", "content_type": "chore", "is_system": False},
    {"slug": TopicSlug.DECISIONS.value, "title": "Решения", "content_type": "decision", "is_system": False},
    {"slug": TopicSlug.NOTES.value, "title": "Заметки", "content_type": "note", "is_system": False},
    {"slug": TopicSlug.TEMPLATES.value, "title": "Шаблоны", "content_type": "template", "is_system": False},
    {"slug": TopicSlug.ARCHIVE.value, "title": "Архив", "content_type": "archive", "is_system": False},
    {"slug": TopicSlug.SYSTEM.value, "title": "Система", "content_type": "system", "is_system": True},
]

BUILTIN_TEMPLATES: dict[str, tuple[str, str]] = {
    "today": (
        "Сегодня",
        "Сегодня\n\nЯ:\n— где:\n— занят(а) с:\n— после работы:\n— важно сегодня:\n\n"
        "Ты:\n— где:\n— занят(а) с:\n— после работы:\n— важно сегодня:\n\n"
        "Вместе:\n— зал / встреча / магазин:\n— купить сегодня:\n— быт на вечер:",
    ),
    "evening": (
        "Вечер",
        "Вечер\n\nСделано:\n—\n—\n\nПеренос:\n—\n—\n\nКупить:\n— сегодня\n— позже\n\n"
        "Быт:\n— стирка / уборка / мусор / продукты\n\nНужны решения:\n—",
    ),
    "week": (
        "Неделя",
        "Неделя\n\nМои фиксированные дни:\n— Пн офис 09:00–18:00\n— Чт офис 09:00–18:00\n"
        "— Пт офис 09:00–16:45\n\nЕё график:\n— Пн–Пт офис примерно 08:00/09:00–18:00\n\n"
        "Совместное:\n— зал:\n— покупки:\n— быт:\n— планы на выходные:\n\nГлавные цели недели:\n1.\n2.\n3.",
    ),
    "purchase": (
        "Покупка",
        "Покупка\n\nКатегория:\nЧто:\nЗачем:\nСрок:\nБюджет:\nКто платит:\nСтатус:\nDriver:\nПодтверждает:",
    ),
    "chore": (
        "Быт",
        "Быт\n\nЗадача:\nЧастота:\nКогда:\nКто:\nСтатус:\nКомментарий:",
    ),
    "decision": (
        "Решение",
        "Решение\n\nВопрос:\nВарианты:\nDriver:\nПодтверждает:\nДо какого времени решить:\nИтог:",
    ),
    "note": (
        "Заметка",
        "Заметка\n\nИдея:\nНужно ли действие:\nСрок:\nВо что преобразовать:",
    ),
}

