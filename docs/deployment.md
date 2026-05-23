# Pocket Pulse — Deployment Guide

## What This Is

A personal Telegram expense-tracking bot that:
- Accepts expense entries via Telegram messages
- Stores them in a cloud database (Turso)
- Sends budget overspend alerts
- Generates reports, charts, and exports
- Supports recurring expenses on a schedule

---

## Architecture

```
You (Telegram) → Telegram Servers → Render (FastAPI + PTB) → Turso (SQLite cloud)
```

| Layer | Tool | Purpose |
|---|---|---|
| Bot framework | python-telegram-bot v22 | Handles commands, conversations, job queue |
| Web server | FastAPI + uvicorn | Receives webhook POSTs from Telegram, serves /health |
| Database | Turso (libsql) | Cloud SQLite — stores expenses, budgets, recurring jobs |
| Hosting | Render (free tier) | Runs the bot 24/7 |
| Keep-alive | UptimeRobot | Pings /health every 5 min so Render never sleeps |

---

## How Webhook Mode Works

Telegram supports two ways to receive updates:

- **Polling** — your bot keeps asking Telegram "any new messages?" in a loop. Simple but requires a persistent always-on connection. Doesn't work on free-tier hosting that sleeps idle processes.
- **Webhook** — you give Telegram an HTTPS URL. Telegram pushes each message to that URL the moment it arrives. Your server only wakes when there's something to do.

We use **webhook mode in production** and **polling locally** (controlled by the `WEBHOOK_URL` env var).

---

## Project Structure

```
expense-bot/
├── bot.py                  # Entry point — FastAPI app + PTB setup
├── requirements.txt        # Python dependencies
├── .python-version         # Pins Python 3.12 for Render
├── db/
│   ├── connection.py       # Turso async wrapper
│   ├── queries.py          # All SQL queries
│   └── schema.py           # Table definitions
├── handlers/
│   ├── add.py              # /add command
│   ├── reports.py          # /report, /summary, /chart, /export
│   ├── budgets.py          # /setbudget, /budgets
│   ├── search.py           # /search
│   ├── settings.py         # /settings
│   └── recurring.py        # Recurring expense scheduler
└── utils/
    ├── parser.py           # Natural language expense parsing
    ├── categorizer.py      # Auto-categorisation
    ├── budget_alert.py     # Overspend detection
    └── charts.py           # Matplotlib chart generation
```

---

## Environment Variables

Set these in Render → your service → **Environment** tab:

| Variable | Example | Description |
|---|---|---|
| `BOT_TOKEN` | `123456:ABC-xyz` | From @BotFather on Telegram |
| `ALLOWED_USER_ID` | `987654321` | Your Telegram user ID (find via @userinfobot) |
| `TURSO_DATABASE_URL` | `libsql://...turso.io` | From Turso dashboard |
| `TURSO_AUTH_TOKEN` | `eyJ...` | From Turso dashboard |
| `WEBHOOK_URL` | `https://pocket-pulse-6nz2.onrender.com/<BOT_TOKEN>` | Your Render URL + bot token as path |
| `WEBHOOK_SECRET` | *(optional)* | Random string for extra security |

---

## How to Deploy (from scratch)

### 1. Push code to GitHub
```bash
git push origin main
```

### 2. Create Render Web Service
1. [render.com](https://render.com) → New → Web Service
2. Connect GitHub repo → select `pocket-pulse`
3. Render auto-detects `render.yaml` — settings are pre-filled:
   - Root Dir: `expense-bot`
   - Build: `pip install -r requirements.txt`
   - Start: `python bot.py`
   - Health Check: `/health`

### 3. Set environment variables
In Render dashboard → Environment → add all variables from the table above.

`WEBHOOK_URL` format:
```
https://<your-render-subdomain>.onrender.com/<BOT_TOKEN>
```

### 4. Verify deployment
Check the webhook is registered:
```
https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```
Healthy response has no `last_error_message` and `pending_update_count: 0`.

### 5. Set up UptimeRobot (prevents Render free tier sleep)
1. [uptimerobot.com](https://uptimerobot.com) → New Monitor
2. Type: HTTP(s)
3. URL: `https://<your-service>.onrender.com/health`
4. Interval: 5 minutes

---

## Local Development

No `WEBHOOK_URL` in your `.env` → bot automatically uses polling mode.

```bash
cd expense-bot
cp .env.example .env   # fill in BOT_TOKEN, ALLOWED_USER_ID, TURSO_*
python bot.py
```

---

## Common Issues Encountered

### `libsql-experimental` build failure
**Symptom:** `No matching distribution found for libsql-experimental>=0.3`  
**Cause:** Version constraint was wrong — package versions are `0.0.x`, not `0.x`  
**Fix:** Changed to `libsql-experimental>=0.0.55` in requirements.txt

### Python 3.14 — no pre-built wheel
**Symptom:** Render picked Python 3.14, `libsql-experimental` tried to compile from Rust source, failed  
**Fix:** Added `.python-version` file pinning Python `3.12`

### 404 on webhook
**Symptom:** `getWebhookInfo` showed `Wrong response from the webhook: 404 Not Found`  
**Cause:** PTB's built-in webhook server listens on `/` by default, but Telegram was posting to `/<token>`  
**Fix:** Switched to FastAPI which explicitly handles the correct path

### 403 on webhook
**Symptom:** `Wrong response from the webhook: 403 Forbidden`  
**Cause:** `secret_token=""` (empty string) caused PTB to reject all requests  
**Fix:** Changed to `secret_token=None` when `WEBHOOK_SECRET` env var is not set

### Service restarts every ~60 seconds
**Symptom:** Render logs showed "Application is stopping" ~60s after each deploy  
**Cause:** Render's health check hits `GET /` — PTB's tornado server has no handler for it, returns 404 → Render marks service unhealthy → restarts  
**Fix:** Replaced PTB's built-in tornado webhook server with FastAPI + uvicorn, added `GET /health` endpoint, set `healthCheckPath: /health` in render.yaml

---

## Render Free Tier Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| Sleeps after 15 min idle | First message after idle has ~30s delay | UptimeRobot pings every 5 min |
| 750 hrs/month compute | Enough for one always-on service | — |
| Shared CPU | Slow cold starts | Font cache pre-builds after first deploy |

Upgrade to Render **Starter ($7/mo)** to eliminate sleep entirely.
