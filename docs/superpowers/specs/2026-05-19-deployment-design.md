# Deployment Design: Pocket Pulse Bot

**Date:** 2026-05-19
**Branch:** feat/expense-bot
**Goal:** Deploy the Telegram expense bot as a free, always-on service accessible any time without running a local machine.

---

## Stack

| Service | Role | Cost | Card required |
|---|---|---|---|
| Render | Hosts the bot process, auto-deploys from GitHub | Free tier | No |
| Turso | Cloud SQLite database (libsql), persists all expense data | Free tier | No |
| UptimeRobot | Pings `/health` every 5 min to prevent Render from sleeping | Free tier | No |

---

## Architecture

```
Telegram  →  POST /webhook/<TOKEN>  →  Render (HTTPS, port 10000)
                                              ↕
                                         Turso (libsql cloud)

UptimeRobot  →  GET /health (every 5 min)  →  Render
```

- Bot switches from **polling** to **webhook** mode. Telegram delivers messages via HTTP POST to the Render URL instead of the bot polling Telegram's API.
- `python-telegram-bot`'s built-in webhook server handles incoming requests — no extra web framework needed.
- A `/health` route returns `200 OK` for UptimeRobot to keep the service awake.
- All expense/budget/recurring data lives in Turso. The bot creates tables on first startup via the existing `schema.create_tables()` call.

---

## Code Changes

### 1. DB driver: `aiosqlite` → `libsql_experimental`

Turso's Python client (`libsql-experimental`) has an async API that mirrors `aiosqlite`. SQL queries are unchanged — only connection setup differs.

**`db/schema.py` and `db/queries.py`:** Replace `aiosqlite.Connection` type hints with `libsql_experimental.Connection`. Connection objects behave identically for `execute`, `executescript`, `fetchone`, `fetchall`, `commit`, `lastrowid`.

**`bot.py`:** Replace `aiosqlite.connect(db_path)` with `libsql_experimental.connect(url=TURSO_URL, auth_token=TURSO_TOKEN)`. The `DB_PATH` env var is no longer used.

### 2. Webhook mode

**`bot.py`:** Replace `app.run_polling(drop_pending_updates=True)` with:

```python
app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 10000)),
    url_path=token,
    webhook_url=f"{os.environ['WEBHOOK_URL']}/{token}",
)
```

### 3. Health endpoint

UptimeRobot only needs an HTTP response to confirm the service is alive — it does not require a `200 OK`. Configure the UptimeRobot monitor with **keyword monitoring disabled** and set it to alert only on no-response (i.e. TCP failure). Point it at the root URL `https://<app>.onrender.com/`. The webhook server returns a non-200 for unknown paths, which is sufficient to keep Render awake. No code change required for this.

### 4. `requirements.txt`

Add:
```
libsql-experimental>=0.3
```

### 5. `render.yaml`

```yaml
services:
  - type: web
    name: pocket-pulse
    runtime: python
    rootDir: expense-bot
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: ALLOWED_USER_ID
        sync: false
      - key: TURSO_DATABASE_URL
        sync: false
      - key: TURSO_AUTH_TOKEN
        sync: false
      - key: WEBHOOK_URL
        sync: false
```

---

## Environment Variables

| Variable | Source |
|---|---|
| `BOT_TOKEN` | Telegram BotFather |
| `ALLOWED_USER_ID` | Your Telegram user ID |
| `TURSO_DATABASE_URL` | Turso dashboard → Connect |
| `TURSO_AUTH_TOKEN` | Turso dashboard → Generate Token |
| `WEBHOOK_URL` | Render app URL (e.g. `https://pocket-pulse-xyz.onrender.com`) |
| `PORT` | Set automatically by Render (default `10000`) |

---

## Setup Order (for user)

1. **Turso:** Create account → create `pocket-pulse` DB → copy URL and token
2. **GitHub:** Push this branch to GitHub (if not already)
3. **Render:** Connect GitHub repo → set root dir to `expense-bot` → add env vars → deploy
4. **UptimeRobot:** Add HTTP monitor → URL = `https://<app>.onrender.com/health` → 5 min interval

---

## What Is Not Changing

- All handlers (`add`, `reports`, `budgets`, `search`, `settings`, `recurring`)
- All SQL queries in `db/queries.py`
- Table schema in `db/schema.py`
- The `owner_only` middleware
- Tests

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Render sleeps despite UptimeRobot | UptimeRobot 5-min interval is well within Render's 15-min sleep threshold |
| Turso free tier limits (500 DBs, 1B row reads/month) | A personal expense bot uses a negligible fraction of these |
| `libsql-experimental` API divergence from `aiosqlite` | API is nearly identical; divergences are in connection init only |
| Webhook secret exposure | Webhook URL uses the bot token as the path, which is already secret |
