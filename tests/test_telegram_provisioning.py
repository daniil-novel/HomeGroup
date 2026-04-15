from __future__ import annotations

from homegroup.domain.enums import TopicSlug
from homegroup.infrastructure.telegram import build_topic_seed_message, is_public_base_url


def test_public_base_url_detection() -> None:
    assert not is_public_base_url("http://localhost:8000")
    assert not is_public_base_url("http://127.0.0.1:18080")
    assert is_public_base_url("https://homegroup.example.com")


def test_topic_seed_message_uses_public_mini_app_url() -> None:
    message = build_topic_seed_message(
        TopicSlug.PURCHASES.value,
        "Покупки",
        base_url="https://homegroup.example.com",
        bot_username="HomeGroupDomBot",
    )

    assert "Покупки" in message
    assert "Mini App: https://homegroup.example.com/mini-app/purchases" in message
    assert "@HomeGroupDomBot" in message


def test_system_topic_seed_message_mentions_commands_without_public_url() -> None:
    message = build_topic_seed_message(
        TopicSlug.SYSTEM.value,
        "Система",
        base_url="http://localhost:8000",
        bot_username="HomeGroupDomBot",
    )

    assert "Команды бота:" in message
    assert "/diagnostics" in message
    assert "Mini App будет активирован" in message
