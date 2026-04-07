from __future__ import annotations

from dataclasses import dataclass

from database.db import Database


@dataclass(frozen=True)
class Account:
    id: int
    login: str
    password: str
    is_full: int
    is_farm: int
    created_at: str


class AccountsRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_by_id(self, account_id: int) -> Account | None:
        row = await self._db.fetchone(
            "SELECT id, login, password, is_full, is_farm, created_at FROM accounts WHERE id = ?;",
            (account_id,),
        )
        if not row:
            return None
        return Account(
            id=int(row["id"]),
            login=str(row["login"]),
            password=str(row["password"]),
            is_full=int(row["is_full"]),
            is_farm=int(row["is_farm"]),
            created_at=str(row["created_at"]),
        )

    async def add(self, login: str, password: str, *, is_full: int, is_farm: int = 0) -> int:
        await self._db.execute(
            "INSERT INTO accounts (login, password, is_full, is_farm) VALUES (?, ?, ?, ?);",
            (login, password, int(is_full), int(is_farm)),
        )
        row = await self._db.fetchone("SELECT last_insert_rowid() AS id;")
        return int(row["id"]) if row else 0

    async def list_all(
        self, *, only_is_full: int | None = None, only_is_farm: int | None = None
    ) -> list[Account]:
        wheres: list[str] = []
        params: list[int] = []
        if only_is_full is not None:
            wheres.append("is_full = ?")
            params.append(int(only_is_full))
        if only_is_farm is not None:
            wheres.append("is_farm = ?")
            params.append(int(only_is_farm))
        where = f"WHERE {' AND '.join(wheres)}" if wheres else ""
        rows = await self._db.fetchall(
            f"SELECT id, login, password, is_full, is_farm, created_at FROM accounts {where} ORDER BY id DESC;",
            tuple(params),
        )
        return [
            Account(
                id=int(r["id"]),
                login=str(r["login"]),
                password=str(r["password"]),
                is_full=int(r["is_full"]),
                is_farm=int(r["is_farm"]),
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]

    async def delete(self, account_id: int) -> bool:
        row = await self._db.fetchone("SELECT id FROM accounts WHERE id = ?;", (account_id,))
        if not row:
            return False
        await self._db.execute("DELETE FROM accounts WHERE id = ?;", (account_id,))
        return True

    async def set_is_full(self, account_id: int, *, is_full: int) -> bool:
        row = await self._db.fetchone("SELECT id FROM accounts WHERE id = ?;", (account_id,))
        if not row:
            return False
        await self._db.execute(
            "UPDATE accounts SET is_full = ? WHERE id = ?;",
            (int(is_full), int(account_id)),
        )
        return True

    async def set_is_farm(self, account_id: int, *, is_farm: int) -> bool:
        row = await self._db.fetchone("SELECT id FROM accounts WHERE id = ?;", (account_id,))
        if not row:
            return False
        await self._db.execute(
            "UPDATE accounts SET is_farm = ? WHERE id = ?;",
            (int(is_farm), int(account_id)),
        )
        return True

    async def count(self) -> int:
        row = await self._db.fetchone("SELECT COUNT(*) AS c FROM accounts;")
        return int(row["c"]) if row else 0
