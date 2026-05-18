import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import queries

VALID_CURRENCIES = {"INR", "USD", "EUR", "GBP", "AED", "SGD"}
CATEGORY_NAME_MAP = {c.lower(): c for c in ["Food", "Transport", "Shopping", "Health", "Bills", "Entertainment", "Other"]}


async def setcurrency_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    args = context.args or []

    if not args:
        await update.message.reply_text(
            "Usage: `/setcurrency INR`\nSupported: " + ", ".join(sorted(VALID_CURRENCIES)),
            parse_mode="Markdown",
        )
        return

    currency = args[0].upper()
    if currency not in VALID_CURRENCIES:
        await update.message.reply_text(
            f"Unsupported currency. Choose from: {', '.join(sorted(VALID_CURRENCIES))}"
        )
        return

    try:
        async with aiosqlite.connect(db_path) as db:
            await queries.get_or_create_user(db, user_id)
            await queries.update_user_currency(db, user_id, currency)
        await update.message.reply_text(f"✅ Currency set to {currency}")
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def addkeyword_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text("Usage: `/addkeyword food biryani`", parse_mode="Markdown")
        return

    cat_raw = args[0].lower()
    category = CATEGORY_NAME_MAP.get(cat_raw)
    if not category:
        await update.message.reply_text(
            f"Unknown category '{args[0]}'. Use: {', '.join(CATEGORY_NAME_MAP.values())}"
        )
        return

    keyword = args[1].lower()
    try:
        async with aiosqlite.connect(db_path) as db:
            ok = await queries.add_keyword_to_category(db, category, keyword)
        if ok:
            await update.message.reply_text(f"✅ Added '{keyword}' to {category}")
        else:
            await update.message.reply_text(f"Category '{category}' not found.")
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


INTRO_TEXT = """👋 Welcome to Pocket Pulse!

💸 *Log an expense*
Just type: `450 zomato` or `450` (then pick a category)

📋 *View & manage*
/last — last 5 expenses with delete buttons
/find <word> — search expenses
/undo — delete last entry

📊 *Reports*
/summary — today / week / month totals
/report — monthly breakdown
/report last month
/report this week
/chart — pie chart
/export — download as Excel

💰 *Budgets*
/setbudget 25000 — overall monthly limit
/setbudget food 6000 — per category limit
/budgets — view usage with progress bars

🔄 *Recurring*
/recurring add — set up a monthly expense
/recurring list — view all recurring
/recurring delete <id> — remove one

⚙️ *Settings*
/setcurrency USD — change currency
/addkeyword food biryani — add custom keyword
/categories — list all categories & keywords"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(INTRO_TEXT, parse_mode="MarkdownV2")


async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_path = context.bot_data["db_path"]
    try:
        async with aiosqlite.connect(db_path) as db:
            cats = await queries.get_categories(db)
        lines = ["📂 Categories & Keywords\n━━━━━━━━━━━━━━━"]
        for c in cats:
            kws = ", ".join(c["keywords"]) if c["keywords"] else "none"
            lines.append(f"• {c['name']}: {kws}")
        await update.message.reply_text("\n".join(lines))
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


def get_handlers():
    return [
        CommandHandler("start", start_command),
        CommandHandler("setcurrency", setcurrency_command),
        CommandHandler("addkeyword", addkeyword_command),
        CommandHandler("categories", categories_command),
    ]
