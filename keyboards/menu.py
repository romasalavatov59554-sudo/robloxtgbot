from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Главное меню (ReplyKeyboard).

    Требование: добавить кнопку в главное меню, которая выдаёт список аккаунтов.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Список аккаунтов")],
            [KeyboardButton(text="🌾 Фарм аккаунты")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
        selective=True,
    )

