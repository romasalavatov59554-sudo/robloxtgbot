from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    primary_admin_id: int
    db_path: Path


def load_config() -> Config:
    """
    Загружает настройки из переменных окружения.

    Для удобства поддерживается файл .env (см. .env.example).
    """
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("Переменная окружения BOT_TOKEN не задана.")

    # Можно задать несколько админов:
    #   ADMIN_IDS=123,456,789
    # либо один:
    #   ADMIN_ID=123
    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
    if admin_ids_raw:
        parts = [p.strip() for p in admin_ids_raw.split(",") if p.strip()]
        if not parts or any(not p.isdigit() for p in parts):
            raise RuntimeError(
                "ADMIN_IDS должен быть списком чисел через запятую, например: 123,456"
            )
        admin_ids = tuple(int(p) for p in parts)
    else:
        admin_id_raw = os.getenv("ADMIN_ID", "").strip()
        if not admin_id_raw.isdigit():
            raise RuntimeError(
                "Переменная окружения ADMIN_ID должна быть числом (Telegram user id)."
            )
        admin_ids = (int(admin_id_raw),)
    primary_admin_id = admin_ids[0]

    db_path_raw = os.getenv("DB_PATH", "data/bot.db").strip()
    db_path = Path(db_path_raw)

    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        primary_admin_id=primary_admin_id,
        db_path=db_path,
    )

