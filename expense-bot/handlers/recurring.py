import aiosqlite
from datetime import date, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from db import queries

AMOUNT, NOTE, CATEGORY, DAY = range(4)

CATEGORY_EMOJI = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛒",
    "Health": "🏥", "Bills": "💡", "Entertainment": "🎬", "Other": "📦",
}


async def recurring_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage:\n`/recurring add` — add new recurring\n`/recurring list` — view all\n`/recurring delete <id>` — remove one",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    subcmd = args[0].lower()
    if subcmd == "list":
        await _recurring_list(update, context)
        return ConversationHandler.END
    elif subcmd == "delete":
        await _recurring_delete(update, context)
        return ConversationHandler.END
    elif subcmd == "add":
        await update.message.reply_text("How much is the recurring amount? (e.g. `15000`)", parse_mode="Markdown")
        return AMOUNT

    await update.message.reply_text("Unknown subcommand. Use: add, list, delete")
    return ConversationHandler.END


async def recv_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a positive number.")
        return AMOUNT

    context.user_data["rec_amount"] = amount
    await update.message.reply_text("What's the description? (e.g. `rent`, `gym`)")
    return NOTE


async def recv_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["rec_note"] = update.message.text.strip()
    db_path = context.bot_data["db_path"]
    async with aiosqlite.connect(db_path) as db:
        cats = await queries.get_categories(db)
    keyboard = []
    row = []
    for cat in cats:
        emoji = CATEGORY_EMOJI.get(cat["name"], "")
        row.append(InlineKeyboardButton(f"{emoji} {cat['name']}", callback_data=f"rcat:{cat['name']}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    await update.message.reply_text("Which category?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CATEGORY


async def recv_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["rec_category"] = query.data.split(":")[1]
    await query.edit_message_text("Which day of the month should this recur? (1–28)")
    return DAY


async def recv_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        day = int(update.message.text.strip())
        if not 1 <= day <= 28:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a day between 1 and 28.")
        return DAY

    ud = context.user_data
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]

    async with aiosqlite.connect(db_path) as db:
        rid = await queries.add_recurring(
            db, user_id, ud["rec_amount"], ud["rec_note"], ud["rec_category"], day
        )

    r = {
        "id": rid, "user_id": user_id, "amount": ud["rec_amount"],
        "note": ud["rec_note"], "category": ud["rec_category"], "day_of_month": day,
    }
    _schedule_recurring_job(context.application, r)

    await update.message.reply_text(
        f"✅ Recurring set: ₹{ud['rec_amount']:.0f} for {ud['rec_note']} on day {day} every month."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def _recurring_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    async with aiosqlite.connect(db_path) as db:
        rows = await queries.get_recurring_for_user(db, user_id)
    if not rows:
        await update.message.reply_text("No recurring expenses set.")
        return
    lines = ["🔄 Recurring Expenses\n━━━━━━━━━━━━━━━"]
    for r in rows:
        emoji = CATEGORY_EMOJI.get(r["category"], "")
        lines.append(f"[{r['id']}] {emoji} ₹{r['amount']:,.0f} — {r['note']} on day {r['day_of_month']}")
    await update.message.reply_text("\n".join(lines))


async def _recurring_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: `/recurring delete <id>`", parse_mode="Markdown")
        return
    try:
        rid = int(args[1])
    except ValueError:
        await update.message.reply_text("Invalid ID.")
        return

    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    async with aiosqlite.connect(db_path) as db:
        deleted = await queries.delete_recurring(db, rid, user_id)

    if deleted:
        jobs = context.application.job_queue.get_jobs_by_name(f"recurring_{rid}")
        for job in jobs:
            job.schedule_removal()
        await update.message.reply_text(f"✅ Recurring #{rid} deleted.")
    else:
        await update.message.reply_text("Not found or already deleted.")


async def recurring_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    r = context.job.data
    db_path = context.bot_data["db_path"]
    today = date.today().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await queries.add_expense(db, r["user_id"], r["amount"], r["category"], r["note"], today)
    await context.bot.send_message(
        chat_id=r["user_id"],
        text=f"🔄 Recurring: ₹{r['amount']:.0f} added under {r['category']} ({r['note']})",
    )


def _schedule_recurring_job(application, r: dict) -> None:
    application.job_queue.run_monthly(
        callback=recurring_job,
        when=time(9, 0),
        day=r["day_of_month"],
        name=f"recurring_{r['id']}",
        data=r,
        chat_id=r["user_id"],
        user_id=r["user_id"],
    )


def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("recurring", recurring_router)],
        states={
            AMOUNT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_amount)],
            NOTE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_note)],
            CATEGORY: [CallbackQueryHandler(recv_category, pattern=r"^rcat:")],
            DAY:      [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_day)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
