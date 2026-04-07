from __future__ import annotations

from database.db import Database


async def init_db(db: Database) -> None:
    """
    Создаёт таблицы при первом запуске.

    accounts: хранит аккаунты в виде login/password.
    tasks: "очередь задач" (outbox) — сообщения, которые должны быть доставлены администратору.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            password TEXT NOT NULL,
            is_full INTEGER NOT NULL DEFAULT 1, -- 1=полный, 0=пустой
            is_farm INTEGER NOT NULL DEFAULT 0, -- 1=на фарме, 0=обычный
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    # Миграция для старых баз: добавляем is_full если его ещё нет.
    rows = await db.fetchall("PRAGMA table_info(accounts);")
    cols = {str(r["name"]) for r in rows}
    if "is_full" not in cols:
        await db.execute("ALTER TABLE accounts ADD COLUMN is_full INTEGER NOT NULL DEFAULT 1;")
    if "is_farm" not in cols:
        await db.execute("ALTER TABLE accounts ADD COLUMN is_farm INTEGER NOT NULL DEFAULT 0;")

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            parse_mode TEXT NOT NULL DEFAULT 'HTML',
            status TEXT NOT NULL DEFAULT 'pending', -- pending/sent/failed
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            sent_at TEXT
        );
        """
    )
