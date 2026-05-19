# Turso Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the local `aiosqlite` SQLite connection with a Turso cloud database (libsql embedded replica) so expense data is stored in the cloud and accessible from anywhere.

**Architecture:** A new `db/connection.py` module wraps `libsql_experimental` with an async-compatible interface that mirrors `aiosqlite`. The bot creates one persistent `Connection` at startup and stores it in `bot_data["db_conn"]`. Handlers retrieve `db_conn` directly instead of opening `aiosqlite.connect(db_path)` each time.

**Tech Stack:** `libsql-experimental` (Turso's Python client), `aiosqlite` (kept for tests only), `python-telegram-bot>=20.0`

---

## File Map

| File | Change |
|---|---|
| `expense-bot/db/connection.py` | **CREATE** — async wrapper around libsql_experimental |
| `expense-bot/requirements.txt` | Add `libsql-experimental>=0.3` |
| `expense-bot/db/schema.py` | Remove `aiosqlite` import, update type hint |
| `expense-bot/db/queries.py` | Remove `aiosqlite` import, update type hints |
| `expense-bot/bot.py` | Use `open_db()` at startup, store `db_conn` in bot_data |
| `expense-bot/handlers/add.py` | Use `db_conn` from bot_data |
| `expense-bot/handlers/reports.py` | Use `db_conn` from bot_data |
| `expense-bot/handlers/budgets.py` | Use `db_conn` from bot_data |
| `expense-bot/handlers/search.py` | Use `db_conn` from bot_data |
| `expense-bot/handlers/settings.py` | Use `db_conn` from bot_data |
| `expense-bot/handlers/recurring.py` | Use `db_conn` from bot_data |
| `expense-bot/tests/conftest.py` | No change — tests keep using `aiosqlite` in-memory |

---

### Task 1: Add `libsql-experimental` to requirements

**Files:**
- Modify: `expense-bot/requirements.txt`

- [ ] **Step 1: Add the dependency**

Open `expense-bot/requirements.txt` and add `libsql-experimental>=0.3` as a new line:

```
python-telegram-bot[job-queue]>=20.0
aiosqlite>=0.19
matplotlib>=3.8
pandas>=2.0
openpyxl>=3.1
python-dotenv>=1.0
libsql-experimental>=0.3
```

- [ ] **Step 2: Install it**

```bash
cd expense-bot
source .venv/bin/activate
pip install libsql-experimental
```

Expected: package installs without error. It's a binary wheel so it downloads fast.

- [ ] **Step 3: Verify import works**

```bash
python -c "import libsql_experimental; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add expense-bot/requirements.txt
git commit -m "chore: add libsql-experimental dependency for Turso"
```

---

### Task 2: Create `db/connection.py`

**Files:**
- Create: `expense-bot/db/connection.py`

This module provides an async `Connection` wrapper around the synchronous `libsql_experimental` API, so all existing handler code can use it without knowing about the underlying driver.

- [ ] **Step 1: Write the module**

Create `expense-bot/db/connection.py` with this content:

```python
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
```

- [ ] **Step 2: Verify syntax**

```bash
cd expense-bot
python -c "from db.connection import open_db, Connection; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add expense-bot/db/connection.py
git commit -m "feat: add async libsql Connection wrapper for Turso"
```

---

### Task 3: Update `db/schema.py` and `db/queries.py` type hints

**Files:**
- Modify: `expense-bot/db/schema.py`
- Modify: `expense-bot/db/queries.py`

The query functions take a `db` connection argument typed as `aiosqlite.Connection`. Since both `aiosqlite.Connection` (used in tests) and the new `Connection` wrapper have the same async interface, we change the type to `Any` so both work.

- [ ] **Step 1: Update `db/schema.py`**

Replace the top of `expense-bot/db/schema.py`:

Old:
```python
import json
import aiosqlite
```

New:
```python
import json
from typing import Any
```

Replace every occurrence of `aiosqlite.Connection` in the file with `Any`.

The full updated `create_tables` signature becomes:
```python
async def create_tables(db: Any) -> None:
```

- [ ] **Step 2: Update `db/queries.py`**

Replace the top of `expense-bot/db/queries.py`:

Old:
```python
import json
from datetime import datetime, timezone
import aiosqlite
```

New:
```python
import json
from datetime import datetime, timezone
from typing import Any
```

Replace every `aiosqlite.Connection` type hint in the file with `Any`. There are ~20 function signatures — use find-and-replace: change `db: aiosqlite.Connection` → `db: Any` throughout the file.

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```bash
cd expense-bot
pytest tests/test_queries.py tests/test_schema.py -v
```

Expected: all tests pass (tests still use `aiosqlite` in-memory — the type hint change has no runtime effect).

- [ ] **Step 4: Commit**

```bash
git add expense-bot/db/schema.py expense-bot/db/queries.py
git commit -m "refactor: replace aiosqlite.Connection type hints with Any"
```

---

### Task 4: Update `bot.py`

**Files:**
- Modify: `expense-bot/bot.py`

Replace `aiosqlite.connect(db_path)` in `post_init` with the persistent `Connection` stored in `bot_data`. Remove `DB_PATH` env var usage.

- [ ] **Step 1: Replace the full `bot.py`**

```python
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, TypeHandler
from telegram.ext import ApplicationHandlerStop

from db import schema, queries
from db.connection import open_db
from handlers import add, reports, budgets, search, settings
from handlers.recurring import get_conversation_handler, _schedule_recurring_job

load_dotenv()
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def owner_only(update: Update, context) -> None:
    """Reject every update that doesn't come from the configured owner."""
    allowed_id = context.bot_data.get("allowed_user_id")
    user = update.effective_user
    if user is None or user.id != allowed_id:
        logger.warning("Blocked unauthorised user_id=%s", user.id if user else "unknown")
        if update.message:
            await update.message.reply_text("This is a private bot.")
        elif update.callback_query:
            await update.callback_query.answer("This is a private bot.", show_alert=True)
        raise ApplicationHandlerStop


async def post_init(application: Application) -> None:
    db = application.bot_data["db_conn"]
    await schema.create_tables(db)
    recurring_list = await queries.get_all_recurring(db)

    for r in recurring_list:
        _schedule_recurring_job(application, r)

    logger.info("DB initialised. %d recurring job(s) scheduled.", len(recurring_list))


def main() -> None:
    token = os.environ["BOT_TOKEN"]
    allowed_user_id = int(os.environ["ALLOWED_USER_ID"])
    turso_url = os.environ["TURSO_DATABASE_URL"]
    turso_token = os.environ["TURSO_AUTH_TOKEN"]

    db_conn = open_db(url=turso_url, auth_token=turso_token)

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.bot_data["db_conn"] = db_conn
    app.bot_data["allowed_user_id"] = allowed_user_id

    app.add_handler(TypeHandler(Update, owner_only), group=-1)
    app.add_handler(get_conversation_handler())

    for handler in (
        add.get_handlers()
        + reports.get_handlers()
        + budgets.get_handlers()
        + search.get_handlers()
        + settings.get_handlers()
    ):
        app.add_handler(handler)

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

```bash
cd expense-bot
python -c "import bot; print('ok')"
```

Expected: `ok` (imports without error)

- [ ] **Step 3: Commit**

```bash
git add expense-bot/bot.py
git commit -m "feat: connect bot to Turso via open_db at startup"
```

---

### Task 5: Update handlers — `add.py`

**Files:**
- Modify: `expense-bot/handlers/add.py`

Replace every `aiosqlite.connect(db_path)` block. The handler gets `db = context.bot_data["db_conn"]` directly.

- [ ] **Step 1: Read the current file**

Read `expense-bot/handlers/add.py` in full before editing.

- [ ] **Step 2: Remove `aiosqlite` import and update all DB call sites**

At the top of the file, remove:
```python
import aiosqlite
```

For every function that does:
```python
db_path = context.bot_data["db_path"]
async with aiosqlite.connect(db_path) as db:
    ...
```

Replace with:
```python
db = context.bot_data["db_conn"]
...
```

The `_get_category_names` helper currently takes `db_path: str`. Change its signature and body:

Old:
```python
async def _get_category_names(db_path: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cats = await queries.get_categories(db)
    return [c["name"] for c in cats]
```

New:
```python
async def _get_category_names(db) -> list[str]:
    cats = await queries.get_categories(db)
    return [c["name"] for c in cats]
```

Update every call site of `_get_category_names(db_path)` to `_get_category_names(db)`.

- [ ] **Step 3: Verify syntax**

```bash
cd expense-bot
python -c "from handlers import add; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add expense-bot/handlers/add.py
git commit -m "feat: use db_conn in add handler"
```

---

### Task 6: Update handlers — `reports.py`, `budgets.py`, `search.py`, `settings.py`, `recurring.py`

**Files:**
- Modify: `expense-bot/handlers/reports.py`
- Modify: `expense-bot/handlers/budgets.py`
- Modify: `expense-bot/handlers/search.py`
- Modify: `expense-bot/handlers/settings.py`
- Modify: `expense-bot/handlers/recurring.py`

Each file has the same pattern: remove `import aiosqlite`, replace `db_path = context.bot_data["db_path"]` + `async with aiosqlite.connect(db_path) as db:` with `db = context.bot_data["db_conn"]`.

- [ ] **Step 1: Update `reports.py`**

Remove `import aiosqlite` from the top.

For every block matching:
```python
db_path = context.bot_data["db_path"]
...
async with aiosqlite.connect(db_path) as db:
    ...
```

Replace with:
```python
db = context.bot_data["db_conn"]
...
```
(keeping all the `await queries.*` calls inside unchanged, just removing the `async with` wrapper)

- [ ] **Step 2: Update `budgets.py`**

Same change: remove `import aiosqlite`, replace `db_path` + `async with aiosqlite.connect` pattern with `db = context.bot_data["db_conn"]`.

- [ ] **Step 3: Update `search.py`**

Same change.

- [ ] **Step 4: Update `settings.py`**

Same change.

- [ ] **Step 5: Update `recurring.py`**

Same change. Note: `recurring.py` also has `_schedule_recurring_job` which doesn't touch the DB — leave that function untouched.

- [ ] **Step 6: Verify all handlers import cleanly**

```bash
cd expense-bot
python -c "from handlers import add, reports, budgets, search, settings; from handlers.recurring import get_conversation_handler; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add expense-bot/handlers/reports.py expense-bot/handlers/budgets.py expense-bot/handlers/search.py expense-bot/handlers/settings.py expense-bot/handlers/recurring.py
git commit -m "feat: use db_conn in all remaining handlers"
```

---

### Task 7: End-to-end smoke test

- [ ] **Step 1: Run the full test suite**

```bash
cd expense-bot
pytest -v
```

Expected: all tests pass. (Tests use `aiosqlite` in-memory via `conftest.py` — unaffected by this change.)

- [ ] **Step 2: Run the bot locally**

```bash
cd expense-bot
python bot.py
```

Expected log output:
```
... — INFO — DB initialised. N recurring job(s) scheduled.
... — INFO — Bot starting...
```

If you see `libsql` sync errors, check that `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set correctly in `.env`.

- [ ] **Step 3: Send a test expense in Telegram**

Open your bot in Telegram. Send: `coffee 150`

Expected: bot replies with category confirmation buttons.

- [ ] **Step 4: Verify data in Turso**

Go to [turso.tech](https://turso.tech) → open `pocket-pulse` database → click **Shell** → run:

```sql
SELECT * FROM expenses ORDER BY id DESC LIMIT 5;
```

Expected: your test expense appears.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: Turso integration complete — expenses stored in cloud SQLite"
```
