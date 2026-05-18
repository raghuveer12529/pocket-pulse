from io import BytesIO
from datetime import date, timedelta
import aiosqlite
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db import queries
from utils.charts import generate_pie_chart

CATEGORY_EMOJI = {
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛒",
    "Health": "🏥", "Bills": "💡", "Entertainment": "🎬", "Other": "📦",
}

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _period_dates(args: list[str]) -> tuple[str, str, str]:
    """Returns (start_date, end_date, label) for the requested period."""
    period = " ".join(args).lower().strip()
    today = date.today()

    if period == "last month":
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        label = f"{MONTH_NAMES[first.month]} {first.year}"
    elif period == "this week":
        first = today - timedelta(days=today.weekday())
        last = today
        label = f"Week of {first.strftime('%b %d')}"
    else:
        first = today.replace(day=1)
        last = today
        label = f"{MONTH_NAMES[today.month]} {today.year}"

    return first.isoformat(), last.isoformat(), label


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    start, end, label = _period_dates(context.args or [])

    try:
        async with aiosqlite.connect(db_path) as db:
            totals = await queries.get_category_totals(db, user_id, start, end)
            overall_budget = await queries.get_budget(db, user_id, "overall")

        if not totals:
            await update.message.reply_text(f"No expenses found for {label}.")
            return

        grand_total = sum(totals.values())
        lines = [f"📊 {label} — ₹{grand_total:,.0f} total", "━━━━━━━━━━━━━━━"]
        for cat, amt in totals.items():
            emoji = CATEGORY_EMOJI.get(cat, "")
            pct = int(amt / grand_total * 100)
            lines.append(f"{emoji} {cat:<14} ₹{amt:>7,.0f}  ({pct}%)")
        lines.append("━━━━━━━━━━━━━━━")
        if overall_budget:
            used_pct = int(grand_total / overall_budget * 100)
            lines.append(f"💰 Budget used: {used_pct}% of ₹{overall_budget:,.0f}")

        await update.message.reply_text("\n".join(lines))
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    year_month = today.strftime("%Y-%m")

    try:
        async with aiosqlite.connect(db_path) as db:
            today_totals = await queries.get_category_totals(db, user_id, today.isoformat(), today.isoformat())
            week_totals = await queries.get_category_totals(db, user_id, week_start, today.isoformat())
            month_total = await queries.get_month_total(db, user_id, year_month)

        today_total = sum(today_totals.values())
        week_total = sum(week_totals.values())
        text = (
            f"📅 Today      ₹{today_total:,.0f}\n"
            f"📆 This week  ₹{week_total:,.0f}\n"
            f"🗓 This month ₹{month_total:,.0f}"
        )
        await update.message.reply_text(text)
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]
    today = date.today()
    start = today.replace(day=1).isoformat()
    label = f"{MONTH_NAMES[today.month]} {today.year}"

    try:
        async with aiosqlite.connect(db_path) as db:
            totals = await queries.get_category_totals(db, user_id, start, today.isoformat())

        if not totals:
            await update.message.reply_text("No expenses this month to chart.")
            return

        bio = generate_pie_chart(totals, label)
        await update.message.reply_photo(photo=bio, caption=f"Spending — {label}")
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db_path = context.bot_data["db_path"]

    try:
        async with aiosqlite.connect(db_path) as db:
            expenses = await queries.get_all_expenses(db, user_id)

        if not expenses:
            await update.message.reply_text("No expenses to export yet.")
            return

        df = pd.DataFrame(expenses)
        df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            for month, group in df.groupby("month"):
                group.drop(columns=["month"]).to_excel(writer, sheet_name=str(month), index=False)
        bio.seek(0)

        filename = f"expenses_{user_id}_{date.today().isoformat()}.xlsx"
        await update.message.reply_document(document=bio, filename=filename)
    except Exception:
        await update.message.reply_text("Something went wrong, please try again.")
        raise


def get_handlers():
    return [
        CommandHandler("report", report_command),
        CommandHandler("summary", summary_command),
        CommandHandler("chart", chart_command),
        CommandHandler("export", export_command),
    ]
