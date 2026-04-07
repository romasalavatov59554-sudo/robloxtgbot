from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def accounts_delete_kb(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"acc_del:{account_id}")]
        ]
    )


def accounts_manage_kb(account_id: int, *, is_full: int, is_farm: int) -> InlineKeyboardMarkup:
    toggle_text = "🔁 В пустой" if int(is_full) == 1 else "🔁 В полный"
    farm_text = "🌾 На фарм" if int(is_farm) == 0 else "⬅️ С фарма"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text, callback_data=f"acc_toggle:{account_id}"
                )
            ],
            [InlineKeyboardButton(text=farm_text, callback_data=f"acc_farm:{account_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"acc_del:{account_id}")],
        ]
    )


def accounts_list_mode_kb(scope: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Полные", callback_data=f"acc_list:{scope}:full"),
                InlineKeyboardButton(text="⚪ Пустые", callback_data=f"acc_list:{scope}:empty"),
            ]
        ]
    )


def accounts_add_mode_kb(token: str, *, allow_full: bool) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    if allow_full:
        buttons.append(
            InlineKeyboardButton(text="✅ Полный", callback_data=f"acc_add:{token}:full")
        )
    buttons.append(
        InlineKeyboardButton(text="⚪ Пустой", callback_data=f"acc_add:{token}:empty")
    )
    buttons.append(
        InlineKeyboardButton(text="✖ Отмена", callback_data=f"acc_add:{token}:cancel")
    )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

