# Pocket Pulse — Telegram Expense Bot

Track expenses via Telegram. Supports auto-categorisation, monthly reports, pie charts, budgets with alerts, recurring expenses, and Excel export.

## Setup

### 1. Create a BotFather token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the token (looks like `1234567890:ABCDEF...`)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set BOT_TOKEN=<your token>
```

### 3. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run

```bash
python bot.py
```

The bot creates `data/expenses.db` automatically on first run.

---

## Commands

| Command | Description |
|---------|-------------|
| Send `450 zomato` | Log ₹450, auto-categorised to Food |
| Send `450` | Log expense, pick category via buttons |
| `/undo` | Delete last expense |
| `/last` | View & delete last 5 expenses |
| `/summary` | Today / this week / this month totals |
| `/report` | Current month breakdown |
| `/report last month` | Previous month report |
| `/report this week` | Current week report |
| `/chart` | Pie chart of current month |
| `/export` | Download all expenses as Excel |
| `/setbudget 25000` | Set ₹25,000 overall monthly budget |
| `/setbudget food 6000` | Set per-category budget |
| `/budgets` | View all budgets with progress bars |
| `/find zomato` | Search expenses by keyword |
| `/recurring add` | Add a monthly recurring expense |
| `/recurring list` | List all recurring |
| `/recurring delete <id>` | Remove a recurring entry |
| `/setcurrency USD` | Change display currency |
| `/addkeyword food biryani` | Add custom keyword to a category |
| `/categories` | List all categories and keywords |

---

## Default Categories

| Category | Auto-matched keywords |
|----------|-----------------------|
| Food | zomato, swiggy, restaurant, lunch, dinner, breakfast, cafe |
| Transport | uber, ola, auto, petrol, fuel, metro, bus |
| Shopping | amazon, flipkart, mall, clothes |
| Health | pharmacy, doctor, hospital, medicine |
| Bills | electricity, wifi, internet, rent, water |
| Entertainment | netflix, movie, spotify, hotstar |
| Other | *(manual selection only)* |

Add your own with `/addkeyword food biryani`.

---

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```
