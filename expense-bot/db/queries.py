import json
from datetime import datetime, timezone
from typing import Any


async def get_or_create_user(db: Any, user_id: int) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
    )
    await db.commit()


async def get_user(db: Any, user_id: int) -> dict:
    async with db.execute(
        "SELECT user_id, currency, timezone FROM users WHERE user_id=?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return {"user_id": user_id, "currency": "INR", "timezone": "Asia/Kolkata"}
    return {"user_id": row[0], "currency": row[1], "timezone": row[2]}


async def add_expense(
    db: Any,
    user_id: int,
    amount: float,
    category: str,
    note: str,
    date: str,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    async with db.execute(
        "INSERT INTO expenses (user_id, amount, category, note, date, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, amount, category, note, date, created_at),
    ) as cur:
        row_id = cur.lastrowid
    await db.commit()
    return row_id


async def get_last_expense_id(db: Any, user_id: int) -> int | None:
    async with db.execute(
        "SELECT id FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else None


async def delete_expense(db: Any, expense_id: int, user_id: int) -> bool:
    async with db.execute(
        "DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, user_id)
    ) as cur:
        deleted = cur.rowcount > 0
    await db.commit()
    return deleted


async def get_category_totals(
    db: Any, user_id: int, start_date: str, end_date: str
) -> dict[str, float]:
    async with db.execute(
        """SELECT category, SUM(amount) FROM expenses
           WHERE user_id=? AND date BETWEEN ? AND ?
           GROUP BY category ORDER BY SUM(amount) DESC""",
        (user_id, start_date, end_date),
    ) as cur:
        rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}


async def get_expenses_for_period(
    db: Any, user_id: int, start_date: str, end_date: str
) -> list[dict]:
    async with db.execute(
        """SELECT id, amount, category, note, date FROM expenses
           WHERE user_id=? AND date BETWEEN ? AND ?
           ORDER BY date DESC""",
        (user_id, start_date, end_date),
    ) as cur:
        rows = await cur.fetchall()
    return [{"id": r[0], "amount": r[1], "category": r[2], "note": r[3], "date": r[4]} for r in rows]


async def get_all_expenses(db: Any, user_id: int) -> list[dict]:
    async with db.execute(
        """SELECT id, amount, category, note, date, created_at FROM expenses
           WHERE user_id=? ORDER BY date DESC""",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [
        {"id": r[0], "amount": r[1], "category": r[2], "note": r[3], "date": r[4], "created_at": r[5]}
        for r in rows
    ]


async def get_month_total(db: Any, user_id: int, year_month: str) -> float:
    async with db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND strftime('%Y-%m',date)=?",
        (user_id, year_month),
    ) as cur:
        (total,) = await cur.fetchone()
    return float(total)


async def get_category_month_total(
    db: Any, user_id: int, category: str, year_month: str
) -> float:
    async with db.execute(
        """SELECT COALESCE(SUM(amount),0) FROM expenses
           WHERE user_id=? AND category=? AND strftime('%Y-%m',date)=?""",
        (user_id, category, year_month),
    ) as cur:
        (total,) = await cur.fetchone()
    return float(total)


async def upsert_budget(
    db: Any, user_id: int, category: str, monthly_limit: float
) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO budgets (user_id, category, monthly_limit) VALUES (?,?,?)",
        (user_id, category, monthly_limit),
    )
    await db.commit()


async def get_budget(db: Any, user_id: int, category: str) -> float | None:
    async with db.execute(
        "SELECT monthly_limit FROM budgets WHERE user_id=? AND category=?", (user_id, category)
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else None


async def get_all_budgets(db: Any, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT category, monthly_limit FROM budgets WHERE user_id=? ORDER BY category",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [{"category": r[0], "monthly_limit": r[1]} for r in rows]


async def get_categories(db: Any) -> list[dict]:
    async with db.execute("SELECT name, keywords FROM categories ORDER BY name") as cur:
        rows = await cur.fetchall()
    return [{"name": r[0], "keywords": json.loads(r[1])} for r in rows]


async def add_keyword_to_category(
    db: Any, category_name: str, keyword: str
) -> bool:
    async with db.execute(
        "SELECT keywords FROM categories WHERE name=?", (category_name,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return False
    keywords = json.loads(row[0])
    if keyword not in keywords:
        keywords.append(keyword)
        await db.execute(
            "UPDATE categories SET keywords=? WHERE name=?",
            (json.dumps(keywords), category_name),
        )
        await db.commit()
    return True


async def get_last_n_expenses(
    db: Any, user_id: int, n: int = 5
) -> list[dict]:
    async with db.execute(
        """SELECT id, amount, category, note, date FROM expenses
           WHERE user_id=? ORDER BY id DESC LIMIT ?""",
        (user_id, n),
    ) as cur:
        rows = await cur.fetchall()
    return [{"id": r[0], "amount": r[1], "category": r[2], "note": r[3], "date": r[4]} for r in rows]


async def search_expenses(
    db: Any, user_id: int, keyword: str, limit: int = 10
) -> list[dict]:
    pattern = f"%{keyword}%"
    async with db.execute(
        """SELECT id, amount, category, note, date FROM expenses
           WHERE user_id=? AND (note LIKE ? OR category LIKE ?)
           ORDER BY id DESC LIMIT ?""",
        (user_id, pattern, pattern, limit),
    ) as cur:
        rows = await cur.fetchall()
    return [{"id": r[0], "amount": r[1], "category": r[2], "note": r[3], "date": r[4]} for r in rows]


async def add_recurring(
    db: Any,
    user_id: int,
    amount: float,
    note: str,
    category: str,
    day_of_month: int,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    async with db.execute(
        "INSERT INTO recurring (user_id, amount, note, category, day_of_month, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, amount, note, category, day_of_month, created_at),
    ) as cur:
        row_id = cur.lastrowid
    await db.commit()
    return row_id


async def get_all_recurring(db: Any) -> list[dict]:
    async with db.execute(
        "SELECT id, user_id, amount, note, category, day_of_month FROM recurring"
    ) as cur:
        rows = await cur.fetchall()
    return [
        {"id": r[0], "user_id": r[1], "amount": r[2], "note": r[3], "category": r[4], "day_of_month": r[5]}
        for r in rows
    ]


async def get_recurring_for_user(db: Any, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT id, amount, note, category, day_of_month FROM recurring WHERE user_id=? ORDER BY id",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [
        {"id": r[0], "amount": r[1], "note": r[2], "category": r[3], "day_of_month": r[4]}
        for r in rows
    ]


async def delete_recurring(
    db: Any, recurring_id: int, user_id: int
) -> bool:
    async with db.execute(
        "DELETE FROM recurring WHERE id=? AND user_id=?", (recurring_id, user_id)
    ) as cur:
        deleted = cur.rowcount > 0
    await db.commit()
    return deleted


async def update_user_currency(
    db: Any, user_id: int, currency: str
) -> None:
    await db.execute(
        "UPDATE users SET currency=? WHERE user_id=?", (currency, user_id)
    )
    await db.commit()
