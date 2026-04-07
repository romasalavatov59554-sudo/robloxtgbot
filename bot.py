from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from settings import load_config
from database.db import Database
from database.schema import init_db
from handlers.admin import admin_router
from services.tasks import restore_pending_tasks


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    cfg = load_config()

    # База данных (SQLite)
    db = Database(db_path=cfg.db_path)
    await db.connect()
    await init_db(db)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(admin_router(cfg, db))

    # При старте восстанавливаем "задачи" (очередь сообщений) из БД.
    # Это полезно, если бот/ПК перезапустили и какое-то сообщение не успело уйти.
    await restore_pending_tasks(bot=bot, db=db, admin_ids=list(cfg.admin_ids))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
