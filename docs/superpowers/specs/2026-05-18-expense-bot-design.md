# Pocket Pulse — Telegram Expense Bot Design

**Date:** 2026-05-18  
**Status:** Approved  
**Approach:** Hybrid C — inline buttons for categorization + ConversationHandler for complex commands

---

## 1. Project Context

Personal Telegram bot for expense tracking, running locally on a personal machine. Single primary user. SQLite via `aiosqlite` for persistence. Python 3.11+, `python-telegram-bot` v20+ (async), polling mode (no webhooks needed).

---

## 2. Architecture & Module Boundaries

```
expense-bot/
  bot.py              — build Application, register handlers, re-hydrate recurring jobs, start polling
  handlers/
    add.py            — free-text MessageHandler + CallbackQueryHandler (category buttons) + /undo
    reports.py        — /report, /summary, /chart, /export
    budgets.py        — /setbudget, /budgets
    settings.py       — /setcurrency, /addkeyword, /categories
    search.py         — /find, /last + inline delete buttons
    recurring.py      — ConversationHandler for /recurring add/list/delete
  db/
    schema.py         — create_tables() + seed default categories; runs at startup (idempotent)
    queries.py        — all async DB functions, parameterized; no inline SQL elsewhere
  utils/
    parser.py         — parse_expense(text) → {amount, note} or raises ParseError
    categorizer.py    — categorize(note, user_id, db) → category name | None
    charts.py         — generate_pie_chart(data, label) → BytesIO (PNG, never touches disk)
    budget_alert.py   — check_and_alert(context, user_id, category, new_total) → sends alert at 80% crossing
  data/
    expenses.db       — SQLite database (gitignored)
  .env                — BOT_TOKEN, DB_PATH (gitignored)
  .env.example
  requirements.txt
  README.md
```

### Data Flow — New Expense

1. Free-text message → `add.py` → `parser.py` extracts `{amount, note}` (raises `ParseError` if invalid)
2. `categorizer.py` matches note against category keywords → returns category name or `None`
3. **If matched:** write to DB → send confirmation → `budget_alert.py` checks thresholds
4. **If no match:** send inline keyboard with all categories
5. User taps button → `CallbackQueryHandler` (callback data: `cat:<category>:<amount>:<note>`) → write to DB → confirm → alert check

The callback data is self-contained — no server-side session state, stateless across restarts.

---

## 3. Database Schema

```sql
expenses (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  amount        REAL NOT NULL,
  category      TEXT NOT NULL,
  note          TEXT,
  date          TEXT NOT NULL,       -- YYYY-MM-DD (user's local date, IST default)
  created_at    TEXT NOT NULL        -- ISO datetime UTC
)

categories (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT UNIQUE NOT NULL,
  keywords      TEXT NOT NULL        -- JSON array, e.g. ["zomato","swiggy"]
)

budgets (
  user_id       INTEGER NOT NULL,
  category      TEXT NOT NULL,       -- "overall" for total monthly budget
  monthly_limit REAL NOT NULL,
  PRIMARY KEY (user_id, category)
)

users (
  user_id       INTEGER PRIMARY KEY,
  currency      TEXT NOT NULL DEFAULT 'INR',
  timezone      TEXT NOT NULL DEFAULT 'Asia/Kolkata'
)

recurring (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  amount        REAL NOT NULL,
  note          TEXT NOT NULL,
  category      TEXT NOT NULL,
  day_of_month  INTEGER NOT NULL,    -- 1–28 (capped to avoid Feb edge cases)
  created_at    TEXT NOT NULL
)
```

**Decisions:**
- `date` as `TEXT` ISO string — SQLite date functions work natively
- `budgets.category = "overall"` handles `/setbudget 25000` without a separate column
- `users` row auto-created on first interaction via `queries.get_or_create_user()`
- `categories` seeded at startup with 7 defaults + keywords via `INSERT OR IGNORE`
- Custom keywords (via `/addkeyword`) update the JSON array in the `categories` row

### Default Categories & Keywords

| Category      | Keywords |
|---------------|----------|
| Food          | zomato, swiggy, restaurant, lunch, dinner, breakfast, cafe |
| Transport     | uber, ola, auto, petrol, fuel, metro, bus |
| Shopping      | amazon, flipkart, mall, clothes |
| Health        | pharmacy, doctor, hospital, medicine |
| Bills         | electricity, wifi, internet, rent, water |
| Entertainment | netflix, movie, spotify, hotstar |
| Other         | *(manual fallback only — never auto-matched)* |

---

## 4. Input Parsing & Categorization

### `parser.py` — `parse_expense(text) → dict`

Accepted formats (first token must be a positive float):
- `"450 food lunch at zomato"` → `{amount: 450.0, note: "food lunch at zomato"}`
- `"450 zomato"` → `{amount: 450.0, note: "zomato"}`
- `"450"` → `{amount: 450.0, note: ""}`

Raises `ParseError` with friendly retry message if first token is not a valid positive number.

### `categorizer.py` — `categorize(note, user_id, db) → str | None`

1. Load all categories + keywords from DB
2. Lowercase note, check each keyword as substring
3. Return first matching category name, or `None`
4. `Other` is never returned — only selectable manually via button

### Inline Category Keyboard

Sent when `categorize()` returns `None`:
```
Bot: "What category for ₹450?"
[🍔 Food] [🚗 Transport] [🛒 Shopping]
[🏥 Health] [💡 Bills] [🎬 Entertainment] [📦 Other]
```
Callback data: `cat:<category>:<pending_key>` where `pending_key = f"{user_id}:{message_id}"`.  
Pending expense `{amount, note}` is held in an in-memory dict in `add.py` with a 5-minute TTL, keyed by `pending_key`. This avoids Telegram's 64-byte callback data limit.

### `/undo`

Queries `MAX(id)` for the user, deletes that row, sends confirmation. No soft delete.

---

## 5. Reports, Charts & Export

### `/report [period]`

Period resolved from command text:
- `/report` → current month
- `/report last month` → previous calendar month
- `/report this week` → Monday to today

Output format:
```
📊 May 2026 — ₹18,450 total
━━━━━━━━━━━━━━━
🍔 Food        ₹5,200  (28%)
🚗 Transport   ₹2,100  (11%)
🛒 Shopping    ₹4,800  (26%)
━━━━━━━━━━━━━━━
💰 Budget used: 74% of ₹25,000
```

Category emoji map is a constant dict in `reports.py`.

### `/summary`

Three separate DB queries (today / this week / this month):
```
📅 Today      ₹320
📆 This week  ₹3,100
🗓 This month ₹18,450
```

### `/chart`

`generate_pie_chart(data: dict[str, float], month_label: str) → BytesIO`
- matplotlib pie chart with tight_layout
- Returns PNG as BytesIO — never written to disk
- Sent via `context.bot.send_photo(chat_id, photo=bio)`

### `/export`

- Fetch all expenses for user
- Group by `YYYY-MM` into sheets via `pd.ExcelWriter` + BytesIO
- Sent via `send_document`, filename: `expenses_<user_id>_<YYYY-MM-DD>.xlsx`

---

## 6. Budgets

### Commands

- `/setbudget 25000` → upsert `budgets(user_id, "overall", 25000)`
- `/setbudget food 6000` → upsert `budgets(user_id, "Food", 6000)` (case-normalized)
- `/budgets` → table with % used and ASCII progress bar: `▓▓▓▓▓░░░░░ 52%`

### Budget Alert (`utils/budget_alert.py`)

Called after every successful expense insert:
1. Fetch per-category limit for the expense's category
2. Compute current month total for that category
3. Alert fires exactly once at the 80% threshold crossing:
   - `previous_total < 0.8 * limit` AND `new_total >= 0.8 * limit`
4. Same check for overall budget
5. Alert format: `⚠️ Food budget 80% used (₹4,800 of ₹6,000)`

---

## 7. Recurring Expenses

### ConversationHandler states (`handlers/recurring.py`)

`/recurring add` — 4 states:
1. Ask amount
2. Ask note/description
3. Ask category (inline buttons)
4. Ask day of month (1–28)

`/recurring list` — formatted table with IDs (outside conversation flow, plain CommandHandler)

`/recurring delete <id>` — deletes DB row + cancels JobQueue job by name `recurring_<id>`

### Startup Re-hydration (`bot.py`)

```python
for r in await queries.get_all_recurring():
    app.job_queue.run_monthly(
        callback=recurring_job,
        day=r.day_of_month,
        when=time(9, 0),
        name=f"recurring_{r.id}",
        data=r
    )
```

DB is the source of truth — no APScheduler job persistence needed.

---

## 8. Search & Last

### `/find <keyword>`

`LIKE %keyword%` on both `note` and `category` columns, returns last 10 matches, formatted list.

### `/last`

Last 5 expenses, each with inline `[🗑 Delete]` button.  
Callback: `del:<expense_id>` → deletes row, edits original message to "Deleted ✅".

---

## 9. Settings

- `/setcurrency INR` — updates `users.currency`
- `/addkeyword food biryani` — appends "biryani" to `categories.keywords` JSON array for "Food"
- `/categories` — lists all categories with their keywords

---

## 10. Error Handling

- All handlers wrapped in try/except; friendly error messages sent to user
- `ParseError` from `parser.py` → "Couldn't parse that. Try: `450 lunch` or just `450`"
- Invalid budget/amount → "Please enter a positive number"
- Unknown commands → ignored (no fallback handler)
- DB errors → logged + "Something went wrong, please try again"

---

## 11. Bot Command Registration

```
/add        - Log an expense
/last       - View & delete recent expenses
/summary    - Quick today/week/month totals
/report     - Monthly breakdown
/chart      - Visual spending pie chart
/export     - Download as Excel
/setbudget  - Set spending limits
/budgets    - View budget usage
/find       - Search expenses
/recurring  - Manage recurring expenses
/undo       - Delete last entry
/settings   - Preferences
```

---

## 12. Configuration

### `.env`
```
BOT_TOKEN=your_token_here
DB_PATH=./data/expenses.db
```

### `requirements.txt`
```
python-telegram-bot[job-queue]>=20.0
aiosqlite>=0.19
matplotlib>=3.8
pandas>=2.0
openpyxl>=3.1
python-dotenv>=1.0
```

Note: `[job-queue]` extra installs APScheduler needed for recurring expenses.

---

## 13. Out of Scope

- Multi-user isolation beyond `user_id` filtering (no auth, personal bot)
- Webhook deployment (polling is sufficient for personal use)
- Docker / systemd setup (run directly with `python bot.py`)
- Currency conversion
- OCR receipt scanning
