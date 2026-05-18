import time as _time
import aiosqlite
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from db import queries
from utils.parser import parse_expense, ParseError
from utils.categorizer import categorize
from utils.budget_alert import check_and_alert

# in-memory store for pending (uncategorized) expenses keyed by f"{user_id}:{message_id}"
_pending: dict[str, dict] = {}

CATEGORY_EMOJI = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛒",
    "Health": "🏥", "Bills": "💡", "Entertainment": "🎬", "Other": "📦",
}


def _store_pending(user_id: int, message_id: int, amount: float, note: str) -> str:
    key = f"{user_id}:{message_id}"
    _pending[key] = {"amount": amount, "note": note, "expires": _time.time() + 300}
    return key


def _pop_pending(key: str) -> dict | None:
    entry = _pending.pop(key, None)
    if entry and _time.time() < entry["expires"]:
        return {"amount": entry["amount"], "note": entry["note"]}
    return None


async def expense_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    try:
        parsed = parse_expense(update.message.text)
    except ParseError:
        await update.message.reply_text(
            "Couldn't parse that. Try:\n`450 lunch` or just `450`",
            parse_mode="Markdown",
        )
        return

    try:
        async with aiosqlite.connect(db_path) as db:
            await queries.get_or_create_user(db, user_id)
            category = await categorize(parsed["note"], db)

        if category:
            await _save_expense(update, context, user_id, parsed["amount"], category, parsed["note"])
        else:
            cats = await _get_category_names(db_path)
            key = _store_pending(user_id, update.message.message_id, parsed["amount"], parsed["note"])
            keyboard = []
            row = []
            for cat in cats:
                emoji = CATEGORY_EMOJI.get(cat, "")
                row.append(InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"cat:{cat}:{key}"))
                if len(row) == 3:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            await update.message.reply_text(
                f"What category for ₹{parsed['amount']:.0f}?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":", 2)
    category = parts[1]
    key = parts[2]
    user_id = update.effective_user.id

    pending = _pop_pending(key)
    if not pending:
        await query.edit_message_text("This selection has expired. Please re-enter your expense.")
        return

    await _save_expense(update, context, user_id, pending["amount"], category, pending["note"])
    await query.message.delete()


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    try:
        async with aiosqlite.connect(db_path) as db:
            last_id = await queries.get_last_expense_id(db, user_id)
            if last_id is None:
                await update.message.reply_text("No expenses to undo.")
                return
            await queries.delete_expense(db, last_id, user_id)
        await update.message.reply_text("↩️ Last expense deleted.")
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def _save_expense(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    amount: float,
    category: str,
    note: str,
) -> None:
    db_path = context.bot_data["db_path"]
    today = date.today().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await queries.add_expense(db, user_id, amount, category, note, today)
    emoji = CATEGORY_EMOJI.get(category, "")
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(f"✅ ₹{amount:.0f} added under {emoji} {category}")
    await check_and_alert(context, user_id, category, amount)


async def _get_category_names(db_path: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cats = await queries.get_categories(db)
    return [c["name"] for c in cats]


def get_handlers():
    return [
        CommandHandler("undo", undo_command),
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d"), expense_message),
        CallbackQueryHandler(category_callback, pattern=r"^cat:"),
    ]
