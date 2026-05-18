# Pocket Pulse — Telegram Expense Bot

A personal expense tracker that lives in Telegram. Log expenses by typing naturally, get monthly reports and pie charts, set budgets with automatic alerts, and manage recurring expenses — all without leaving the chat.

---

## Setup

### Step 1 — Create your bot on Telegram

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. `Pocket Pulse`) and a username (e.g. `mypocketpulse_bot`)
4. Copy the token BotFather gives you — it looks like `1234567890:ABCDefgh...`

### Step 2 — Configure environment

```bash
cd expense-bot
cp .env.example .env
```

Open `.env` and paste your token:

```
BOT_TOKEN=1234567890:ABCDefghijklmnop...
DB_PATH=./data/expenses.db
```

### Step 3 — Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4 — Run the bot

```bash
python bot.py
```

The bot creates `data/expenses.db` automatically. Keep this terminal open — the bot only responds while it's running.

### Step 5 — Open Telegram and start

Search for your bot by username, tap **Start**, or send `/start`. You'll see the full command list.

---

## Logging Expenses

Just type in the chat — no command needed.

### Auto-categorised (keyword match)

```
450 zomato          → ✅ ₹450 added under 🍔 Food
200 uber to office  → ✅ ₹200 added under 🚗 Transport
1299 netflix        → ✅ ₹1,299 added under 🎬 Entertainment
15000 rent          → ✅ ₹15,000 added under 💡 Bills
```

### Pick category via buttons

When no keyword matches, the bot asks:

```
You:  350 groceries
Bot:  What category for ₹350?
      [🍔 Food] [🚗 Transport] [🛒 Shopping]
      [🏥 Health] [💡 Bills] [🎬 Entertainment]
      [📦 Other] [➕ New Category]
```

Tap any button to save instantly.

### Create a new category on the fly

Tap **➕ New Category**, then type a name:

```
Bot:  Type a name for the new category (for ₹350):
You:  Groceries
Bot:  ✅ ₹350 added under 📦 Groceries
      📂 'Groceries' saved as a new category
```

The new category is now available for all future expenses.

### Amount only

```
450   → Bot shows category buttons, you tap one
```

### Undo last entry

```
/undo   → ↩️ Last expense deleted
```

---

## Viewing Expenses

### Last 5 expenses with delete buttons

```
/last
```

Each entry shows a 🗑 Delete button. Tap it to remove that entry — the message updates to "Deleted ✅".

### Search by keyword

```
/find zomato      → all expenses with "zomato" in the note or category
/find rent        → all rent entries
/find food        → all Food category entries
```

Returns the 10 most recent matches.

---

## Reports

### Quick totals

```
/summary

📅 Today      ₹320
📆 This week  ₹3,100
🗓 This month ₹18,450
```

### Monthly breakdown

```
/report

📊 May 2026 — ₹18,450 total
━━━━━━━━━━━━━━━
🍔 Food        ₹5,200  (28%)
🚗 Transport   ₹2,100  (11%)
🛒 Shopping    ₹4,800  (26%)
🏥 Health        ₹800   (4%)
💡 Bills       ₹5,550  (30%)
━━━━━━━━━━━━━━━
💰 Budget used: 74% of ₹25,000
```

**Other report periods:**

```
/report last month    → previous calendar month
/report this week     → Monday to today
```

### Pie chart

```
/chart   → sends a PNG chart of current month spending by category
```

### Export to Excel

```
/export   → downloads expenses_<id>_<date>.xlsx
```

One sheet per month, all columns included (amount, category, note, date).

---

## Budgets

### Set a budget

```
/setbudget 25000          → ₹25,000 overall monthly cap
/setbudget food 6000      → ₹6,000 cap for Food only
/setbudget transport 3000 → ₹3,000 cap for Transport only
```

### View budget usage

```
/budgets

📋 Your Budgets
━━━━━━━━━━━━━━━
🍔 Food
  ▓▓▓▓▓▓▓▓░░ 80%
  ₹4,800 / ₹6,000
💰 overall
  ▓▓▓▓▓▓▓░░░ 74%
  ₹18,450 / ₹25,000
```

### Automatic alerts

When any budget crosses 80%, you get an automatic warning — once per crossing, no spam:

```
⚠️ Food budget 80% used (₹4,800 of ₹6,000)
⚠️ Overall budget 80% used (₹20,100 of ₹25,000)
```

---

## Recurring Expenses

Set up monthly expenses that are added automatically at 9 AM on the configured day.

### Add a recurring expense

```
/recurring add

Bot:  How much is the recurring amount?
You:  15000
Bot:  What's the description?
You:  rent
Bot:  Which category? [buttons]
You:  tap 💡 Bills
Bot:  Which day of the month? (1–28)
You:  1
Bot:  ✅ Recurring set: ₹15,000 for rent on day 1 every month.
```

### View all recurring

```
/recurring list

🔄 Recurring Expenses
━━━━━━━━━━━━━━━
[1] 💡 ₹15,000 — rent on day 1
[2] 🎬 ₹199 — netflix on day 5
[3] 🏥 ₹500 — gym on day 10
```

### Delete a recurring entry

```
/recurring delete 2   → removes netflix, cancels the monthly job
```

Use the ID shown in `/recurring list`.

---

## Settings & Customisation

### Change currency symbol

```
/setcurrency USD    → switches to USD
/setcurrency INR    → back to INR (default)
```

Supported: INR, USD, EUR, GBP, AED, SGD

### Add keywords to a category

The bot auto-categorises based on keywords. Add your own:

```
/addkeyword food biryani        → "350 biryani" now maps to Food
/addkeyword transport rapido    → "120 rapido" now maps to Transport
/addkeyword shopping myntra     → "2000 myntra" now maps to Shopping
```

### List all categories and keywords

```
/categories

📂 Categories & Keywords
━━━━━━━━━━━━━━━
• Bills: electricity, wifi, internet, rent, water
• Entertainment: netflix, movie, spotify, hotstar
• Food: zomato, swiggy, restaurant, lunch, dinner, breakfast, cafe, biryani
• Health: pharmacy, doctor, hospital, medicine
• Other:
• Shopping: amazon, flipkart, mall, clothes
• Transport: uber, ola, auto, petrol, fuel, metro, bus
```

---

## Default Categories & Keywords

| Category | Auto-matched keywords |
|----------|-----------------------|
| 🍔 Food | zomato, swiggy, restaurant, lunch, dinner, breakfast, cafe |
| 🚗 Transport | uber, ola, auto, petrol, fuel, metro, bus |
| 🛒 Shopping | amazon, flipkart, mall, clothes |
| 🏥 Health | pharmacy, doctor, hospital, medicine |
| 💡 Bills | electricity, wifi, internet, rent, water |
| 🎬 Entertainment | netflix, movie, spotify, hotstar |
| 📦 Other | *(manual selection only)* |

New categories can be created on the fly during expense entry, or keywords added with `/addkeyword`.

---

## Quick Reference

| What you want | What to type |
|---|---|
| Log an expense | `450 zomato` |
| Log without keyword | `450` then tap a button |
| Create new category | tap ➕ New Category when prompted |
| Undo last | `/undo` |
| See recent | `/last` |
| Search | `/find <keyword>` |
| Today's total | `/summary` |
| Month report | `/report` |
| Pie chart | `/chart` |
| Export to Excel | `/export` |
| Set overall budget | `/setbudget 25000` |
| Set category budget | `/setbudget food 6000` |
| Check budgets | `/budgets` |
| Add recurring | `/recurring add` |
| List recurring | `/recurring list` |
| Delete recurring | `/recurring delete <id>` |
| Change currency | `/setcurrency USD` |
| Add keyword | `/addkeyword food biryani` |
| See categories | `/categories` |

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```
