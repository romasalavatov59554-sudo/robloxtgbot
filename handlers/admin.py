from __future__ import annotations

import re
import secrets
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.accounts_repo import AccountsRepo
from database.db import Database
from keyboards.accounts import (
    accounts_add_mode_kb,
    accounts_list_mode_kb,
    accounts_manage_kb,
)
from keyboards.menu import main_menu_kb
from services.tasks import enqueue_task
from utils.auth import protect_router


def _format_accounts_html(
    items: list[tuple[int, str, str, str]], *, mode: str
) -> str:
    if not items:
        return (
            "<b>Аккаунтов пока нет</b>\n\n"
            "Просто отправьте сообщение в формате:\n"
            "<code>Ник:Пароль</code>"
        )

    lines: list[str] = ["<b>Список аккаунтов</b>"]
    lines.append(f"<i>Всего:</i> <b>{len(items)}</b>\n")
    for idx, (acc_id, login, password, created_at) in enumerate(items, start=1):
        # Пароль всегда показываем админу. Для "пустых" он будет пустым.
        cred = f"{login}:{password}"
        lines.append(
            f"• <b>№{idx}</b> (<code>#{acc_id}</code>) — <code>{cred}</code>"
        )
    lines.append(
        "\n<b>Действия по номерам № (одним сообщением)</b>\n"
        "<code>del 1,2,3</code> — удалить\n"
        "<code>farm 1-3</code> — на фарм / с фарма\n"
        "<code>full 1 2 3</code> — сделать полными\n"
        "<code>empty 2,4</code> — сделать пустыми"
    )
    return "\n".join(lines)


def admin_router(cfg, db: Database) -> Router:
    """
    Роутер админского функционала.

    Без FSM: добавление идёт обычным сообщением "Ник:Пароль".
    """
    router = Router(name="admin")
    protect_router(router, set(cfg.admin_ids))

    repo = AccountsRepo(db)

    # Простое "ожидание выбора" без FSM: держим в памяти на короткое время.
    # token -> (ts, [(login, password), ...])
    pending_add: dict[str, tuple[float, list[tuple[str, str]]]] = {}
    pending_ttl_s = 10 * 60

    # Соответствие номеров "№1, №2..." из последнего показанного списка к реальным id.
    # chat_id -> (ts, scope, {idx: account_id})
    # scope: "main" | "farm"
    last_list: dict[int, tuple[float, str, dict[int, int]]] = {}
    last_list_ttl_s = 20 * 60

    def _cleanup_last_list(now: float) -> None:
        for chat_id, (ts, _, _) in list(last_list.items()):
            if now - ts > last_list_ttl_s:
                last_list.pop(chat_id, None)

    def _parse_indices(text: str) -> list[int]:
        raw = re.split(r"[,\s]+", text.strip())
        out: list[int] = []
        for part in raw:
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                if a.isdigit() and b.isdigit():
                    start = int(a)
                    end = int(b)
                    if start <= end:
                        out.extend(range(start, end + 1))
                    else:
                        out.extend(range(end, start + 1))
                continue
            if part.isdigit():
                out.append(int(part))
        seen: set[int] = set()
        uniq: list[int] = []
        for x in out:
            if x <= 0 or x in seen:
                continue
            seen.add(x)
            uniq.append(x)
        return uniq

    @router.message(F.text == "/start")
    async def start_cmd(message: Message) -> None:
        await message.answer(
            "<b>Готово.</b>\n\n"
            "Отправьте аккаунт в формате:\n"
            "<code>Ник:Пароль</code>\n\n"
            "Или нажмите кнопку <b>📋 Список аккаунтов</b>.",
            reply_markup=main_menu_kb(),
        )

    @router.message(F.text == "ℹ️ Помощь")
    async def help_btn(message: Message) -> None:
        await message.answer(
            "<b>Как пользоваться</b>\n\n"
            "<b>Добавление аккаунтов</b>\n"
            "- Один аккаунт: <code>Ник:Пароль</code> или <code>Ник</code>\n"
            "- Несколько аккаунтов: одним сообщением, каждый с новой строки:\n"
            "  <code>user1:pass1</code>\n"
            "  <code>user2:pass2</code>\n\n"
            "После отправки бот спросит: сохранить как <b>✅ полный</b> или <b>⚪ пустой</b>.\n\n"
            "<b>Списки</b>\n"
            "- <b>📋 Список аккаунтов</b>: выбрать <b>✅ Полные</b> / <b>⚪ Пустые</b>\n"
            "- <b>🌾 Фарм аккаунты</b>: сразу весь список фарма (без выбора)\n\n"
            "<b>Номера №</b>\n"
            "- В списках показывается <b>№1, №2…</b> (это счётчик)\n"
            "- В скобках показывается <code>#id</code> (внутренний id)\n\n"
            "<b>Действия по номерам № (одним сообщением)</b>\n"
            "<code>del 1,2,3</code> — удалить\n"
            "<code>farm 1-3</code> — на фарм / с фарма\n"
            "<code>full 1 2 3</code> — сделать полными\n"
            "<code>empty 2,4</code> — сделать пустыми\n\n"
            "<i>Важно:</i> команды работают по номерам из <b>последнего показанного списка</b>.\n"
            "Если команда отправлена из списка фарма — <code>full</code>/<code>empty</code> "
            "также снимают аккаунты с фарма (переносят в основной список).",
            reply_markup=main_menu_kb(),
        )

    @router.message(F.text == "📋 Список аккаунтов")
    async def list_btn(message: Message) -> None:
        await message.answer(
            "<b>Какой список показать?</b>",
            reply_markup=accounts_list_mode_kb("main"),
        )

    @router.message(F.text == "🌾 Фарм аккаунты")
    async def list_farm_btn(message: Message) -> None:
        accounts = await repo.list_all(only_is_farm=1)
        html = _format_accounts_html(
            [(a.id, a.login, a.password, a.created_at) for a in accounts],
            mode="farm",
        )
        await message.answer(html, reply_markup=main_menu_kb())
        # Запомним соответствие № -> id для пакетных действий.
        last_list[int(message.chat.id)] = (
            time.time(),
            "farm",
            {i: a.id for i, a in enumerate(accounts, start=1)},
        )

    @router.callback_query(F.data.startswith("acc_list:"))
    async def list_mode(call: CallbackQuery) -> None:
        # acc_list:{scope}:{mode}
        parts = (call.data or "").split(":")
        if len(parts) != 3:
            await call.answer("Некорректно.", show_alert=True)
            return
        scope = parts[1]
        mode = parts[2]
        if scope not in {"main", "farm"} or mode not in {"full", "empty"}:
            await call.answer("Некорректно.", show_alert=True)
            return

        only_is_full = 1 if mode == "full" else 0
        only_is_farm = 1 if scope == "farm" else 0
        accounts = await repo.list_all(only_is_full=only_is_full, only_is_farm=only_is_farm)
        html = _format_accounts_html(
            [(a.id, a.login, a.password, a.created_at) for a in accounts],
            mode=mode,
        )

        if not accounts:
            if call.message:
                await call.message.answer(html, reply_markup=main_menu_kb())
            await call.answer()
            return

        if call.message:
            await call.message.answer(html, reply_markup=main_menu_kb())
        await call.answer()
        if call.message:
            last_list[int(call.message.chat.id)] = (
                time.time(),
                scope,
                {i: a.id for i, a in enumerate(accounts, start=1)},
            )
        # Важно: не шлём по сообщению на аккаунт — всё в одном сообщении выше.

    @router.callback_query(F.data.startswith("acc_del:"))
    async def delete_account(call: CallbackQuery) -> None:
        acc_id = int(call.data.split(":", 1)[1])
        ok = await repo.delete(acc_id)
        if ok:
            await call.answer("Удалено.")
            # Обновим сообщение, чтобы было видно результат.
            if call.message:
                await call.message.edit_text("<b>Удалено.</b>")
        else:
            await call.answer("Не найдено.", show_alert=True)

    @router.callback_query(F.data.startswith("acc_toggle:"))
    async def toggle_account_type(call: CallbackQuery) -> None:
        acc_id = int(call.data.split(":", 1)[1])
        acc = await repo.get_by_id(acc_id)
        if not acc:
            await call.answer("Не найдено.", show_alert=True)
            return

        new_is_full = 0 if acc.is_full == 1 else 1
        ok = await repo.set_is_full(acc_id, is_full=new_is_full)
        if not ok:
            await call.answer("Не найдено.", show_alert=True)
            return

        type_label = "✅ полный" if new_is_full == 1 else "⚪ пустой"
        if call.message:
            await call.message.edit_text(
                f"<b>#{acc.id}</b> ({type_label}) — <code>{acc.login}:{acc.password}</code>",
                reply_markup=accounts_manage_kb(acc.id, is_full=new_is_full, is_farm=acc.is_farm),
            )
        await call.answer("Готово.")

    @router.callback_query(F.data.startswith("acc_farm:"))
    async def toggle_account_farm(call: CallbackQuery) -> None:
        acc_id = int(call.data.split(":", 1)[1])
        acc = await repo.get_by_id(acc_id)
        if not acc:
            await call.answer("Не найдено.", show_alert=True)
            return

        new_is_farm = 0 if acc.is_farm == 1 else 1
        ok = await repo.set_is_farm(acc_id, is_farm=new_is_farm)
        if not ok:
            await call.answer("Не найдено.", show_alert=True)
            return

        type_label = "✅ полный" if acc.is_full == 1 else "⚪ пустой"
        farm_label = "🌾 фарм" if new_is_farm == 1 else "📋 обычный"
        if call.message:
            await call.message.edit_text(
                f"<b>#{acc.id}</b> ({type_label}, {farm_label}) — <code>{acc.login}:{acc.password}</code>",
                reply_markup=accounts_manage_kb(acc.id, is_full=acc.is_full, is_farm=new_is_farm),
            )
        await call.answer("Готово.")

    @router.callback_query(F.data.startswith("acc_add:"))
    async def add_account_choose_mode(call: CallbackQuery) -> None:
        # acc_add:{token}:{mode}
        parts = (call.data or "").split(":")
        if len(parts) != 3:
            await call.answer("Некорректно.", show_alert=True)
            return

        token = parts[1]
        mode = parts[2]
        if mode not in {"full", "empty", "cancel"}:
            await call.answer("Некорректно.", show_alert=True)
            return

        item = pending_add.pop(token, None)
        if not item:
            await call.answer("Время выбора истекло. Отправьте аккаунт ещё раз.", show_alert=True)
            return

        ts, batch = item
        if time.time() - ts > pending_ttl_s:
            await call.answer("Время выбора истекло. Отправьте аккаунт ещё раз.", show_alert=True)
            return

        if mode == "cancel":
            await call.answer("Отменено.")
            if call.message:
                await call.message.edit_text("<b>Отменено.</b>")
            return

        is_full = 1 if mode == "full" else 0
        saved_ids: list[int] = []
        for login, password in batch:
            new_id = await repo.add(login=login, password=password, is_full=is_full)
            saved_ids.append(new_id)

        if call.message:
            await call.message.edit_text(
                f"<b>Сохранено.</b> Добавлено аккаунтов: <b>{len(saved_ids)}</b>"
            )
            preview_lines: list[str] = []
            for i, ((login, password), acc_id) in enumerate(zip(batch, saved_ids), start=1):
                if i > 30:
                    break
                show = f"{login}:{password}"
                preview_lines.append(
                    f"• <b>№{i}</b> (<code>#{acc_id}</code>) — <code>{show}</code>"
                )
            more = "" if len(saved_ids) <= 30 else f"\n<i>…и ещё {len(saved_ids) - 30}</i>"
            await call.message.answer(
                "<b>Добавлено:</b>\n" + "\n".join(preview_lines) + more,
                reply_markup=main_menu_kb(),
            )

        # Лог в tasks: одно сообщение на весь батч (чтобы не спамить)
        preview = "\n".join([f"• <code>{l}:{p}</code>" for l, p in batch[:20]])
        more = "" if len(batch) <= 20 else f"\n<i>…и ещё {len(batch) - 20}</i>"
        await enqueue_task(
            db=db,
            admin_id=cfg.primary_admin_id,
            text=(
                f"<b>Добавлены аккаунты</b> ({len(saved_ids)} шт., "
                f"{'полные' if is_full == 1 else 'пустые'}):\n{preview}{more}"
            ),
        )
        await call.answer("Сохранено.")

    @router.message(F.text)
    async def add_account_any_text(message: Message) -> None:
        text = (message.text or "").strip()
        now = time.time()
        _cleanup_last_list(now)

        # Пакетные действия по номерам № из последнего показанного списка:
        #   del 1,2,3
        #   farm 1-3
        #   full 1 2 3
        #   empty 2,4
        low = text.lower()
        if low.startswith(("del ", "farm ", "full ", "empty ")):
            parts = low.split(None, 1)
            if len(parts) != 2:
                await message.answer(
                    "Формат:\n"
                    "<code>del 1,2,3</code>\n"
                    "<code>farm 1-3</code>\n"
                    "<code>full 1 2 3</code>\n"
                    "<code>empty 2,4</code>",
                    reply_markup=main_menu_kb(),
                )
                return

            action, rest = parts[0], parts[1]
            indices = _parse_indices(rest)
            if not indices:
                await message.answer("Не нашёл номера. Пример: <code>del 1,2,3</code>")
                return

            entry = last_list.get(int(message.chat.id))
            if not entry:
                await message.answer(
                    "Сначала открой список (чтобы появились номера №), потом отправь команду.\n"
                    "Например: <code>del 1,2</code>",
                    reply_markup=main_menu_kb(),
                )
                return

            ts, scope, mapping = entry
            if now - ts > last_list_ttl_s:
                last_list.pop(int(message.chat.id), None)
                await message.answer(
                    "Список устарел. Открой список заново и повтори.",
                    reply_markup=main_menu_kb(),
                )
                return

            ids: list[int] = []
            missing: list[int] = []
            for idx in indices:
                acc_id = mapping.get(idx)
                if acc_id is None:
                    missing.append(idx)
                else:
                    ids.append(acc_id)

            if not ids:
                await message.answer("Номера не найдены в последнем списке.")
                return

            done: list[int] = []
            not_found: list[int] = []

            if action == "del":
                for acc_id in ids:
                    ok = await repo.delete(acc_id)
                    (done if ok else not_found).append(acc_id)
            elif action == "farm":
                for acc_id in ids:
                    acc = await repo.get_by_id(acc_id)
                    if not acc:
                        not_found.append(acc_id)
                        continue
                    new_is_farm = 0 if acc.is_farm == 1 else 1
                    ok = await repo.set_is_farm(acc_id, is_farm=new_is_farm)
                    (done if ok else not_found).append(acc_id)
            elif action in {"full", "empty"}:
                new_is_full = 1 if action == "full" else 0
                for acc_id in ids:
                    ok_full = await repo.set_is_full(acc_id, is_full=new_is_full)
                    ok = ok_full
                    # Если команда пришла из фарм-списка — "перемещаем" в основной список:
                    # меняем full/empty и снимаем с фарма.
                    if ok_full and scope == "farm":
                        ok = await repo.set_is_farm(acc_id, is_farm=0)
                    (done if ok else not_found).append(acc_id)

            msg_lines: list[str] = []
            if done:
                msg_lines.append(f"<b>Готово:</b> <code>{', '.join(map(str, done))}</code>")
            if not_found:
                msg_lines.append(f"<b>Не найдено:</b> <code>{', '.join(map(str, not_found))}</code>")
            if missing:
                msg_lines.append(f"<b>Нет в списке №:</b> <code>{', '.join(map(str, missing))}</code>")
            msg_lines.append("\nОткрой список заново, чтобы обновились номера №.")
            await message.answer("\n".join(msg_lines), reply_markup=main_menu_kb())
            return

        if not text:
            await message.answer(
                "Отправьте аккаунты (каждый с новой строки):\n"
                "<code>Ник:Пароль</code>\n"
                "<code>Ник2:Пароль2</code>\n\n"
                "Или один аккаунт: <code>Ник:Пароль</code> / <code>Ник</code>",
                reply_markup=main_menu_kb(),
            )
            return

        # Поддержка пакетного ввода: каждая строка = отдельный аккаунт
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        batch: list[tuple[str, str]] = []
        for ln in lines:
            if ":" in ln:
                login, password = ln.split(":", 1)
                login = login.strip()
                password = password.strip()
            else:
                login = ln.strip()
                password = ""

            if not login:
                continue
            batch.append((login, password))

        if not batch:
            await message.answer(
                "Не удалось распознать аккаунты.\n"
                "Пример:\n"
                "<code>user1:pass1</code>\n"
                "<code>user2:pass2</code>",
                reply_markup=main_menu_kb(),
            )
            return

        # Чистим протухшие pending, чтобы словарь не рос.
        for k, (ts, _) in list(pending_add.items()):
            if now - ts > pending_ttl_s:
                pending_add.pop(k, None)

        token = secrets.token_urlsafe(6)
        pending_add[token] = (now, batch)

        preview_lines = []
        for login, password in batch[:10]:
            preview_lines.append(f"• <code>{login}:{password}</code>")
        preview = "\n".join(preview_lines)
        more = "" if len(batch) <= 10 else f"\n<i>…и ещё {len(batch) - 10}</i>"

        await message.answer(
            "<b>Как сохранить аккаунт?</b>\n\n"
            f"<b>Найдено:</b> <b>{len(batch)}</b>\n{preview}{more}\n\n"
            "Выберите тип для <b>всех</b> этих аккаунтов:\n"
            "✅ <b>Полные</b> или ⚪ <b>Пустые</b>",
            reply_markup=accounts_add_mode_kb(token, allow_full=True),
        )

    return router

