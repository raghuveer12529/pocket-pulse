import aiosqlite
from datetime import date
from db import queries


async def check_and_alert(
    context,
    user_id: int,
    category: str,
    expense_amount: float,
) -> None:
    """Fire a one-time alert when spending crosses 80% of a budget limit."""
    db_path = context.bot_data["db_path"]
    year_month = date.today().strftime("%Y-%m")

    async with aiosqlite.connect(db_path) as db:
        cat_limit = await queries.get_budget(db, user_id, category)
        if cat_limit:
            new_total = await queries.get_category_month_total(db, user_id, category, year_month)
            prev_total = new_total - expense_amount
            if prev_total < 0.8 * cat_limit <= new_total:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ {category} budget 80% used (₹{new_total:.0f} of ₹{cat_limit:.0f})",
                )

        overall_limit = await queries.get_budget(db, user_id, "overall")
        if overall_limit:
            new_overall = await queries.get_month_total(db, user_id, year_month)
            prev_overall = new_overall - expense_amount
            if prev_overall < 0.8 * overall_limit <= new_overall:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Overall budget 80% used (₹{new_overall:.0f} of ₹{overall_limit:.0f})",
                )
