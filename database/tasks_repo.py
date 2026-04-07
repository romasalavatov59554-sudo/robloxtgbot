from __future__ import annotations

from dataclasses import dataclass

from database.db import Database


@dataclass(frozen=True)
class TaskRow:
    id: int
    admin_id: int
    text: str
    parse_mode: str
    status: str
    created_at: str
    sent_at: str | None


class TasksRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def enqueue(self, admin_id: int, text: str, parse_mode: str = "HTML") -> int:
        await self._db.execute(
            "INSERT INTO tasks (admin_id, text, parse_mode, status) VALUES (?, ?, ?, 'pending');",
            (admin_id, text, parse_mode),
        )
        row = await self._db.fetchone("SELECT last_insert_rowid() AS id;")
        return int(row["id"]) if row else 0

    async def list_pending(self, admin_id: int) -> list[TaskRow]:
        rows = await self._db.fetchall(
            """
            SELECT id, admin_id, text, parse_mode, status, created_at, sent_at
            FROM tasks
            WHERE admin_id = ? AND status = 'pending'
            ORDER BY id ASC;
            """,
            (admin_id,),
        )
        return [
            TaskRow(
                id=int(r["id"]),
                admin_id=int(r["admin_id"]),
                text=str(r["text"]),
                parse_mode=str(r["parse_mode"]),
                status=str(r["status"]),
                created_at=str(r["created_at"]),
                sent_at=(str(r["sent_at"]) if r["sent_at"] is not None else None),
            )
            for r in rows
        ]

    async def mark_sent(self, task_id: int) -> None:
        await self._db.execute(
            "UPDATE tasks SET status = 'sent', sent_at = datetime('now') WHERE id = ?;",
            (task_id,),
        )

    async def mark_failed(self, task_id: int) -> None:
        await self._db.execute(
            "UPDATE tasks SET status = 'failed' WHERE id = ?;",
            (task_id,),
        )
