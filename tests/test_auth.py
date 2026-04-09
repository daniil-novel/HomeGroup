from __future__ import annotations

from homegroup.infrastructure.config import Settings
from homegroup.presentation.auth import verify_telegram_init_data


def test_debug_mode_allows_empty_init_data() -> None:
    settings = Settings(debug=True, bot_token="token")
    assert verify_telegram_init_data("", settings)


def test_non_debug_mode_rejects_empty_init_data() -> None:
    settings = Settings(debug=False, bot_token="token")
    assert not verify_telegram_init_data("", settings)

