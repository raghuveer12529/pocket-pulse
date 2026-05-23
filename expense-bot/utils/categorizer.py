from db.queries import get_categories

_cache: list[dict] = []


async def categorize(note: str, db) -> str | None:
    """Returns the first matching category name, or None. Never returns 'Other'."""
    if not note:
        return None
    global _cache
    if not _cache:
        _cache = await get_categories(db)
    note_lower = note.lower()
    for cat in _cache:
        if cat["name"] == "Other":
            continue
        for keyword in cat["keywords"]:
            if keyword in note_lower:
                return cat["name"]
    return None


def invalidate_cache() -> None:
    global _cache
    _cache = []
