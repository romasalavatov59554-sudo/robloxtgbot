from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from settings import load_config
from database.db import Database
from database.schema import init_db
from handlers.admin import admin_router
from services.tasks import restore_pending_tasks


async def _run_health_server() -> None:
    """
    Leapcell reverse proxy expects an HTTP server on port 8080 and pings /kaithheathcheck.
    We run a tiny health endpoint alongside polling.
    """

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/kaithheathcheck", health)
    # Some Leapcell probes use a different spelling.
    app.router.add_get("/kaithhealthcheck", health)
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    # Keep running forever (until cancelled).
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


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
        # Run health HTTP server + polling together.
        await asyncio.gather(
            _run_health_server(),
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        )
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
