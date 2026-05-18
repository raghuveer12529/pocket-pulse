import pytest
from unittest.mock import AsyncMock, MagicMock
import aiosqlite
from db.schema import create_tables
from db import queries
from utils.budget_alert import check_and_alert

USER = 222

@pytest.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    async with aiosqlite.connect(path) as db:
        await create_tables(db)
        await queries.get_or_create_user(db, USER)
    return path

def make_context(db_path: str):
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot_data = {"db_path": db_path}
    return ctx

async def test_alert_does_not_fire_below_80(db_path):
    async with aiosqlite.connect(db_path) as db:
        await queries.upsert_budget(db, USER, "Food", 1000.0)
        await queries.add_expense(db, USER, 50.0, "Food", "a", "2026-05-01")
        await queries.add_expense(db, USER, 700.0, "Food", "b", "2026-05-02")

    ctx = make_context(db_path)
    await check_and_alert(ctx, USER, "Food", 700.0)
    ctx.bot.send_message.assert_not_called()

async def test_alert_fires_when_crossing_80(db_path):
    async with aiosqlite.connect(db_path) as db:
        await queries.upsert_budget(db, USER, "Food", 1000.0)
        await queries.add_expense(db, USER, 750.0, "Food", "a", "2026-05-01")
        await queries.add_expense(db, USER, 100.0, "Food", "b", "2026-05-02")

    ctx = make_context(db_path)
    await check_and_alert(ctx, USER, "Food", 100.0)
    ctx.bot.send_message.assert_called_once()
    text = ctx.bot.send_message.call_args[1]["text"]
    assert "80%" in text

async def test_no_alert_when_already_over_80(db_path):
    async with aiosqlite.connect(db_path) as db:
        await queries.upsert_budget(db, USER, "Food", 1000.0)
        await queries.add_expense(db, USER, 900.0, "Food", "a", "2026-05-01")
        await queries.add_expense(db, USER, 50.0, "Food", "b", "2026-05-02")

    ctx = make_context(db_path)
    await check_and_alert(ctx, USER, "Food", 50.0)
    ctx.bot.send_message.assert_not_called()

async def test_no_alert_when_no_budget_set(db_path):
    async with aiosqlite.connect(db_path) as db:
        await queries.add_expense(db, USER, 500.0, "Food", "a", "2026-05-01")

    ctx = make_context(db_path)
    await check_and_alert(ctx, USER, "Food", 500.0)
    ctx.bot.send_message.assert_not_called()

async def test_overall_budget_alert(db_path):
    async with aiosqlite.connect(db_path) as db:
        await queries.upsert_budget(db, USER, "overall", 1000.0)
        await queries.add_expense(db, USER, 750.0, "Food", "a", "2026-05-01")
        await queries.add_expense(db, USER, 100.0, "Transport", "b", "2026-05-02")

    ctx = make_context(db_path)
    await check_and_alert(ctx, USER, "Transport", 100.0)
    ctx.bot.send_message.assert_called_once()
