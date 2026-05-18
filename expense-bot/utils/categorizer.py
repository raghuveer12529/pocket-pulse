import aiosqlite
from db.queries import get_categories

async def categorize(note: str, db: aiosqlite.Connection) -> str | None:
    """Returns the first matching category name, or None. Never returns 'Other'."""
    if not note:
        return None
    note_lower = note.lower()
    categories = await get_categories(db)
    for cat in categories:
        if cat["name"] == "Other":
            continue
        for keyword in cat["keywords"]:
            if keyword in note_lower:
                return cat["name"]
    return None
