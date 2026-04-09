from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl

from homegroup.infrastructure.config import Settings


def verify_telegram_init_data(init_data: str, settings: Settings) -> bool:
    if settings.debug and not init_data:
        return True
    if not init_data:
        return False
    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = parsed.pop("hash", None)
    if received_hash is None or not settings.bot_token:
        return False
    data_check_string = "\n".join(f"{key}={parsed[key]}" for key in sorted(parsed))
    secret_key = hmac.new(
        b"WebAppData",
        settings.bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)

