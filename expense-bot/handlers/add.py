import time as _time
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

# tracks users who tapped "New Category" and are typing a category name: user_id -> pending_key
_awaiting_new_cat: dict[int, str] = {}

CATEGORY_EMOJI = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛒",
    "Health": "🏥", "Bills": "💡", "Entertainment": "🎬", "Other": "📦",
}


class _AwaitingNewCatFilter(filters.MessageFilter):
    def filter(self, message) -> bool:
        return bool(message.from_user and message.from_user.id in _awaiting_new_cat)

_awaiting_cat_filter = _AwaitingNewCatFilter()


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
    db = context.bot_data["db_conn"]
    try:
        parsed = parse_expense(update.message.text)
    except ParseError:
        await update.message.reply_text(
            "Couldn't parse that. Try:\n`450 lunch` or just `450`",
            parse_mode="Markdown",
        )
        return

    try:
        await queries.get_or_create_user(db, user_id)
        category = await categorize(parsed["note"], db)

        if category:
            await _save_expense(update, context, user_id, parsed["amount"], category, parsed["note"])
        else:
            cats = await _get_category_names(db)
            key = _store_pending(user_id, update.message.message_id, parsed["amount"], parsed["note"])
            keyboard = _build_category_keyboard(cats, key)
            await update.message.reply_text(
                f"What category for ₹{parsed['amount']:.0f}?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def newcat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped '➕ New Category' — ask them to type the name."""
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    user_id = update.effective_user.id

    pending = _pending.get(key)
    if not pending or _time.time() >= pending["expires"]:
        await query.edit_message_text("This selection has expired. Please re-enter your expense.")
        return

    _awaiting_new_cat[user_id] = key
    amount = pending["amount"]
    await query.edit_message_text(f"Type a name for the new category (for ₹{amount:.0f}):")


async def new_category_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User typed a new category name after tapping '➕ New Category'."""
    user_id = update.effective_user.id
    key = _awaiting_new_cat.pop(user_id, None)
    if not key:
        return

    category_name = update.message.text.strip().title()
    if not category_name:
        await update.message.reply_text("Category name can't be empty. Please re-enter your expense.")
        return

    pending = _pop_pending(key)
    if not pending:
        await update.message.reply_text("Selection expired. Please re-enter your expense.")
        return

    db = context.bot_data["db_conn"]
    await db.execute(
        "INSERT OR IGNORE INTO categories (name, keywords) VALUES (?, ?)",
        (category_name, "[]"),
    )
    await db.commit()
    await queries.add_expense(db, user_id, pending["amount"], category_name, pending["note"], date.today().isoformat())

    await update.message.reply_text(
        f"✅ ₹{pending['amount']:.0f} added under 📦 {category_name}\n"
        f"📂 '{category_name}' saved as a new category"
    )
    await check_and_alert(context, user_id, category_name, pending["amount"])


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

    # Auto-learn: save the note as a keyword so next time it resolves without the picker
    note = pending["note"]
    if note:
        db = context.bot_data["db_conn"]
        await queries.add_keyword_to_category(db, category, note.lower().strip())

    await _save_expense(update, context, user_id, pending["amount"], category, note)
    await query.message.delete()


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db = context.bot_data["db_conn"]
    try:
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
    db = context.bot_data["db_conn"]
    today = date.today().isoformat()
    await queries.add_expense(db, user_id, amount, category, note, today)
    emoji = CATEGORY_EMOJI.get(category, "")
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(f"✅ ₹{amount:.0f} added under {emoji} {category}")
    await check_and_alert(context, user_id, category, amount)


async def _get_category_names(db) -> list[str]:
    cats = await queries.get_categories(db)
    return [c["name"] for c in cats]


def _build_category_keyboard(cats: list[str], key: str) -> list[list[InlineKeyboardButton]]:
    keyboard = []
    row = []
    for cat in cats:
        emoji = CATEGORY_EMOJI.get(cat, "📦")
        row.append(InlineKeyboardButton(f"{emoji} {cat}", callback_data=f"cat:{cat}:{key}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("➕ New Category", callback_data=f"newcat:{key}")])
    return keyboard


def get_handlers():
    return [
        CommandHandler("undo", undo_command),
        # _awaiting_cat_filter must come before the digit-only expense_message handler
        MessageHandler(filters.TEXT & ~filters.COMMAND & _awaiting_cat_filter, new_category_message),
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d"), expense_message),
        CallbackQueryHandler(newcat_callback, pattern=r"^newcat:"),
        CallbackQueryHandler(category_callback, pattern=r"^cat:"),
    ]
