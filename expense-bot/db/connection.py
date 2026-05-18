from __future__ import annotations
import libsql_experimental as libsql


class _Cursor:
    def __init__(self, raw) -> None:
        self._raw = raw

    async def fetchone(self):
        return self._raw.fetchone()

    async def fetchall(self):
        return self._raw.fetchall()

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    @property
    def lastrowid(self):
        return self._raw.lastrowid

    async def __aenter__(self) -> _Cursor:
        return self

    async def __aexit__(self, *_) -> None:
        pass


class _ExecCtx:
    """Supports both `await db.execute(...)` and `async with db.execute(...) as cur:`."""

    __slots__ = ("_raw_conn", "_sql", "_params", "_cursor")

    def __init__(self, raw_conn, sql: str, params) -> None:
        self._raw_conn = raw_conn
        self._sql = sql
        self._params = params
        self._cursor = None

    def __await__(self):
        return self._run().__await__()

    async def _run(self) -> _Cursor:
        return _Cursor(self._raw_conn.execute(self._sql, self._params))

    async def __aenter__(self) -> _Cursor:
        self._cursor = _Cursor(self._raw_conn.execute(self._sql, self._params))
        return self._cursor

    async def __aexit__(self, *_) -> None:
        pass


class Connection:
    """Async-compatible wrapper around a libsql_experimental connection."""

    def __init__(self, raw) -> None:
        self._raw = raw

    def execute(self, sql: str, params=()) -> _ExecCtx:
        return _ExecCtx(self._raw, sql, params)

    async def executescript(self, sql: str) -> None:
        self._raw.executescript(sql)

    async def commit(self) -> None:
        self._raw.commit()
        self._raw.sync()

    async def __aenter__(self) -> Connection:
        return self

    async def __aexit__(self, *_) -> None:
        pass


def open_db(url: str, auth_token: str, local_path: str = "data/local_replica.db") -> Connection:
    """Open a libsql embedded replica synced with Turso and return an async wrapper."""
    import os
    os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
    raw = libsql.connect(local_path, sync_url=url, auth_token=auth_token)
    raw.sync()
    return Connection(raw)
