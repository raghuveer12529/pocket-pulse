import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from db import queries

CATEGORY_EMOJI = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛒",
    "Health": "🏥", "Bills": "💡", "Entertainment": "🎬", "Other": "📦",
}


def _format_expense(e: dict) -> str:
    emoji = CATEGORY_EMOJI.get(e["category"], "")
    note = f" — {e['note']}" if e["note"] else ""
    return f"{emoji} ₹{e['amount']:,.0f} [{e['category']}]{note} on {e['date']}"


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    keyword = " ".join(context.args or []).strip()

    if not keyword:
        await update.message.reply_text(
            "Usage: `/find <keyword>`\nExample: `/find zomato`", parse_mode="Markdown"
        )
        return

    try:
        async with aiosqlite.connect(db_path) as db:
            results = await queries.search_expenses(db, user_id, keyword)

        if not results:
            await update.message.reply_text(f"No expenses found matching '{keyword}'.")
            return

        lines = [f"🔍 Results for '{keyword}':\n"]
        for e in results:
            lines.append(_format_expense(e))
        await update.message.reply_text("\n".join(lines))
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]

    try:
        async with aiosqlite.connect(db_path) as db:
            expenses = await queries.get_last_n_expenses(db, user_id, 5)

        if not expenses:
            await update.message.reply_text("No expenses yet.")
            return

        for e in expenses:
            text = _format_expense(e)
            keyboard = [[InlineKeyboardButton("🗑 Delete", callback_data=f"del:{e['id']}")]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def delete_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    expense_id = int(query.data.split(":")[1])
    db_path = context.bot_data["db_path"]

    try:
        async with aiosqlite.connect(db_path) as db:
            deleted = await queries.delete_expense(db, expense_id, user_id)

        if deleted:
            await query.edit_message_text("Deleted ✅")
        else:
            await query.edit_message_text("Already deleted or not found.")
    except Exception:
        await query.edit_message_text("Something went wrong.")
        raise


def get_handlers():
    return [
        CommandHandler("find", find_command),
        CommandHandler("last", last_command),
        CallbackQueryHandler(delete_expense_callback, pattern=r"^del:"),
    ]
