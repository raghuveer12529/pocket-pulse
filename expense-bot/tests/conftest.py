import pytest
import libsql_experimental as libsql
from db.connection import Connection
from db.schema import create_tables

@pytest.fixture
async def db():
    conn = Connection(libsql.connect(":memory:"))
    await create_tables(conn)
    yield conn
