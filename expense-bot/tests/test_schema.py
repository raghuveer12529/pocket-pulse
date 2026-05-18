import aiosqlite
import pytest
from db.schema import create_tables

async def test_tables_exist():
    async with aiosqlite.connect(":memory:") as db:
        await create_tables(db)
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cur:
            tables = {r[0] async for r in cur}
    assert {"expenses", "categories", "budgets", "users", "recurring"}.issubset(tables)

async def test_default_categories_seeded():
    async with aiosqlite.connect(":memory:") as db:
        await create_tables(db)
        async with db.execute("SELECT name FROM categories ORDER BY name") as cur:
            names = [r[0] async for r in cur]
    assert "Food" in names
    assert "Transport" in names
    assert "Other" in names
    assert len(names) == 7

async def test_create_tables_idempotent():
    async with aiosqlite.connect(":memory:") as db:
        await create_tables(db)
        await create_tables(db)  # should not raise
        async with db.execute("SELECT COUNT(*) FROM categories") as cur:
            (count,) = await cur.fetchone()
    assert count == 7
