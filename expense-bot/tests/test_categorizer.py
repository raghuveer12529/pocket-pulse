import pytest
import json
import aiosqlite
from db.schema import create_tables
from utils.categorizer import categorize

@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await create_tables(conn)
    yield conn
    await conn.close()

async def test_match_by_keyword(db):
    result = await categorize("lunch at zomato", db)
    assert result == "Food"

async def test_match_transport(db):
    result = await categorize("took uber to office", db)
    assert result == "Transport"

async def test_match_case_insensitive(db):
    result = await categorize("NETFLIX subscription", db)
    assert result == "Entertainment"

async def test_no_match_returns_none(db):
    result = await categorize("some random thing", db)
    assert result is None

async def test_other_not_auto_matched(db):
    result = await categorize("", db)
    assert result is None

async def test_custom_keyword_matches(db):
    await db.execute(
        "UPDATE categories SET keywords=? WHERE name='Food'",
        (json.dumps(["zomato", "swiggy", "biryani"]),),
    )
    await db.commit()
    result = await categorize("biryani from paradise", db)
    assert result == "Food"
