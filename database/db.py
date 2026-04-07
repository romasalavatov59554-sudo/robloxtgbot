from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import aiosqlite


@dataclass
class Database:
    db_path: Path
    _conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path.as_posix())
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._conn.execute("PRAGMA journal_mode = WAL;")
        await self._conn.execute("PRAGMA synchronous = NORMAL;")
        await self._conn.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        await self.conn.execute(sql, tuple(params))
        await self.conn.commit()

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[aiosqlite.Row]:
        cur = await self.conn.execute(sql, tuple(params))
        row = await cur.fetchone()
        await cur.close()
        return row

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(sql, tuple(params))
        rows = await cur.fetchall()
        await cur.close()
        return list(rows)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
