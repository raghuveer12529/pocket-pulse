import aiosqlite
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import queries

CATEGORY_EMOJI = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛒",
    "Health": "🏥", "Bills": "💡", "Entertainment": "🎬",
    "Other": "📦", "overall": "💰",
}

CATEGORY_NAME_MAP = {c.lower(): c for c in ["Food", "Transport", "Shopping", "Health", "Bills", "Entertainment", "Other"]}


def _progress_bar(pct: int) -> str:
    filled = min(pct // 10, 10)
    return "▓" * filled + "░" * (10 - filled) + f" {pct}%"


async def setbudget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    args = context.args or []

    try:
        if len(args) == 1:
            limit = float(args[0])
            if limit <= 0:
                raise ValueError
            category = "overall"
            display = "overall"
        elif len(args) == 2:
            cat_raw = args[0].lower()
            category = CATEGORY_NAME_MAP.get(cat_raw)
            if not category:
                await update.message.reply_text(
                    f"Unknown category '{args[0]}'. Use: {', '.join(CATEGORY_NAME_MAP.values())}"
                )
                return
            limit = float(args[1])
            if limit <= 0:
                raise ValueError
            display = category
        else:
            await update.message.reply_text(
                "Usage:\n`/setbudget 25000` — overall\n`/setbudget food 6000` — per category",
                parse_mode="Markdown",
            )
            return

        async with aiosqlite.connect(db_path) as db:
            await queries.get_or_create_user(db, user_id)
            await queries.upsert_budget(db, user_id, category, limit)

        await update.message.reply_text(f"✅ {display} budget set to ₹{limit:,.0f}/month")
    except ValueError:
        await update.message.reply_text("Please enter a positive number for the limit.")
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def budgets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    year_month = date.today().strftime("%Y-%m")

    try:
        async with aiosqlite.connect(db_path) as db:
            budgets = await queries.get_all_budgets(db, user_id)
            if not budgets:
                await update.message.reply_text("No budgets set. Use /setbudget to add one.")
                return

            lines = ["📋 Your Budgets\n━━━━━━━━━━━━━━━"]
            for b in budgets:
                cat = b["category"]
                limit = b["monthly_limit"]
                if cat == "overall":
                    spent = await queries.get_month_total(db, user_id, year_month)
                else:
                    spent = await queries.get_category_month_total(db, user_id, cat, year_month)
                pct = int(min(spent / limit * 100, 100))
                emoji = CATEGORY_EMOJI.get(cat, "")
                bar = _progress_bar(pct)
                lines.append(f"{emoji} {cat}\n  {bar}\n  ₹{spent:,.0f} / ₹{limit:,.0f}")

        await update.message.reply_text("\n".join(lines))
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


def get_handlers():
    return [
        CommandHandler("setbudget", setbudget_command),
        CommandHandler("budgets", budgets_command),
    ]
