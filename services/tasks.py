from __future__ import annotations

import logging

from aiogram import Bot

from database.db import Database
from database.tasks_repo import TasksRepo

log = logging.getLogger(__name__)


async def enqueue_task(db: Database, admin_id: int, text: str, parse_mode: str = "HTML") -> int:
    """
    Сохраняет "задачу" (сообщение) в БД.

    При рестарте бота pending-задачи будут восстановлены и отправлены.
    """
    return await TasksRepo(db).enqueue(admin_id=admin_id, text=text, parse_mode=parse_mode)


async def restore_pending_tasks(bot: Bot, db: Database, admin_ids: list[int]) -> None:
    """
    Восстанавливает pending-задачи из БД и пытается отправить администратору.
    """
    repo = TasksRepo(db)
    for admin_id in admin_ids:
        pending = await repo.list_pending(admin_id=admin_id)
        if not pending:
            continue
        for task in pending:
            try:
                await bot.send_message(chat_id=task.admin_id, text=task.text)
                await repo.mark_sent(task.id)
            except Exception:
                log.exception("Failed to send task id=%s", task.id)
                await repo.mark_failed(task.id)

