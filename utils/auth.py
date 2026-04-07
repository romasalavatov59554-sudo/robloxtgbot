from __future__ import annotations

from aiogram import Router
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message


class AdminOnly(Filter):
    """
    Пропускает апдейты только от администратора.

    Так никто кроме вас не сможет добавлять/удалять/смотреть аккаунты.
    """

    def __init__(self, admin_ids: set[int]) -> None:
        self._admin_ids = admin_ids

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        from_user = getattr(event, "from_user", None)
        return bool(from_user and from_user.id in self._admin_ids)


def protect_router(router: Router, admin_ids: set[int]) -> Router:
    router.message.filter(AdminOnly(admin_ids))
    router.callback_query.filter(AdminOnly(admin_ids))
    return router

