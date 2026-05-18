import pytest
from datetime import date
from db import queries

USER = 111

async def test_get_or_create_user(db):
    await queries.get_or_create_user(db, USER)
    async with db.execute("SELECT currency FROM users WHERE user_id=?", (USER,)) as cur:
        row = await cur.fetchone()
    assert row[0] == "INR"

async def test_get_or_create_user_idempotent(db):
    await queries.get_or_create_user(db, USER)
    await queries.get_or_create_user(db, USER)
    async with db.execute("SELECT COUNT(*) FROM users WHERE user_id=?", (USER,)) as cur:
        (count,) = await cur.fetchone()
    assert count == 1

async def test_add_and_get_last_expense(db):
    await queries.get_or_create_user(db, USER)
    eid = await queries.add_expense(db, USER, 450.0, "Food", "lunch", "2026-05-18")
    assert isinstance(eid, int)
    last_id = await queries.get_last_expense_id(db, USER)
    assert last_id == eid

async def test_delete_expense(db):
    await queries.get_or_create_user(db, USER)
    eid = await queries.add_expense(db, USER, 200.0, "Transport", "uber", "2026-05-18")
    deleted = await queries.delete_expense(db, eid, USER)
    assert deleted is True
    last_id = await queries.get_last_expense_id(db, USER)
    assert last_id is None

async def test_delete_expense_wrong_user(db):
    await queries.get_or_create_user(db, USER)
    eid = await queries.add_expense(db, USER, 200.0, "Food", "lunch", "2026-05-18")
    deleted = await queries.delete_expense(db, eid, 999)
    assert deleted is False

async def test_get_category_totals(db):
    await queries.get_or_create_user(db, USER)
    await queries.add_expense(db, USER, 100.0, "Food", "lunch", "2026-05-18")
    await queries.add_expense(db, USER, 200.0, "Food", "dinner", "2026-05-18")
    await queries.add_expense(db, USER, 50.0, "Transport", "bus", "2026-05-18")
    totals = await queries.get_category_totals(db, USER, "2026-05-01", "2026-05-31")
    assert totals["Food"] == 300.0
    assert totals["Transport"] == 50.0

async def test_upsert_and_get_budget(db):
    await queries.get_or_create_user(db, USER)
    await queries.upsert_budget(db, USER, "Food", 6000.0)
    limit = await queries.get_budget(db, USER, "Food")
    assert limit == 6000.0

async def test_upsert_budget_updates_existing(db):
    await queries.get_or_create_user(db, USER)
    await queries.upsert_budget(db, USER, "Food", 6000.0)
    await queries.upsert_budget(db, USER, "Food", 8000.0)
    limit = await queries.get_budget(db, USER, "Food")
    assert limit == 8000.0

async def test_get_budget_not_set(db):
    await queries.get_or_create_user(db, USER)
    limit = await queries.get_budget(db, USER, "Food")
    assert limit is None

async def test_get_categories(db):
    cats = await queries.get_categories(db)
    names = [c["name"] for c in cats]
    assert "Food" in names
    assert "Other" in names

async def test_add_keyword_to_category(db):
    ok = await queries.add_keyword_to_category(db, "Food", "biryani")
    assert ok is True
    cats = await queries.get_categories(db)
    food = next(c for c in cats if c["name"] == "Food")
    assert "biryani" in food["keywords"]

async def test_add_keyword_unknown_category(db):
    ok = await queries.add_keyword_to_category(db, "Unknown", "test")
    assert ok is False

async def test_get_last_n_expenses(db):
    await queries.get_or_create_user(db, USER)
    for i in range(7):
        await queries.add_expense(db, USER, float(i * 10), "Food", f"item{i}", "2026-05-18")
    rows = await queries.get_last_n_expenses(db, USER, 5)
    assert len(rows) == 5

async def test_search_expenses(db):
    await queries.get_or_create_user(db, USER)
    await queries.add_expense(db, USER, 450.0, "Food", "zomato biryani", "2026-05-18")
    await queries.add_expense(db, USER, 200.0, "Transport", "uber", "2026-05-18")
    results = await queries.search_expenses(db, USER, "biryani")
    assert len(results) == 1
    assert results[0]["note"] == "zomato biryani"

async def test_add_and_get_recurring(db):
    await queries.get_or_create_user(db, USER)
    rid = await queries.add_recurring(db, USER, 15000.0, "rent", "Bills", 1)
    assert isinstance(rid, int)
    rows = await queries.get_recurring_for_user(db, USER)
    assert len(rows) == 1
    assert rows[0]["amount"] == 15000.0

async def test_delete_recurring(db):
    await queries.get_or_create_user(db, USER)
    rid = await queries.add_recurring(db, USER, 500.0, "gym", "Health", 5)
    ok = await queries.delete_recurring(db, rid, USER)
    assert ok is True
    rows = await queries.get_recurring_for_user(db, USER)
    assert rows == []

async def test_update_user_currency(db):
    await queries.get_or_create_user(db, USER)
    await queries.update_user_currency(db, USER, "USD")
    user = await queries.get_user(db, USER)
    assert user["currency"] == "USD"

async def test_get_category_month_total(db):
    await queries.get_or_create_user(db, USER)
    await queries.add_expense(db, USER, 100.0, "Food", "a", "2026-05-10")
    await queries.add_expense(db, USER, 200.0, "Food", "b", "2026-05-15")
    await queries.add_expense(db, USER, 50.0, "Food", "c", "2026-04-01")
    total = await queries.get_category_month_total(db, USER, "Food", "2026-05")
    assert total == 300.0

async def test_get_month_total(db):
    await queries.get_or_create_user(db, USER)
    await queries.add_expense(db, USER, 100.0, "Food", "a", "2026-05-10")
    await queries.add_expense(db, USER, 50.0, "Transport", "b", "2026-05-12")
    total = await queries.get_month_total(db, USER, "2026-05")
    assert total == 150.0

async def test_get_all_expenses(db):
    await queries.get_or_create_user(db, USER)
    await queries.add_expense(db, USER, 100.0, "Food", "a", "2026-05-01")
    await queries.add_expense(db, USER, 200.0, "Food", "b", "2026-04-01")
    rows = await queries.get_all_expenses(db, USER)
    assert len(rows) == 2
