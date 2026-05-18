import pytest
import aiosqlite
from db.schema import create_tables

@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await create_tables(conn)
    yield conn
    await conn.close()
