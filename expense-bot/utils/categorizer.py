from db.queries import get_categories

_cache: list[dict] = []


async def _ensure_cache(db) -> None:
    global _cache
    if not _cache:
        _cache = await get_categories(db)


async def categorize(note: str, db) -> str | None:
    """Returns the first matching category name, or None. Never returns 'Other'."""
    if not note:
        return None
    await _ensure_cache(db)
    note_lower = note.lower()
    for cat in _cache:
        if cat["name"] == "Other":
            continue
        for keyword in cat["keywords"]:
            if keyword in note_lower:
                return cat["name"]
    return None


async def get_cached_category_names(db) -> list[str]:
    await _ensure_cache(db)
    return [c["name"] for c in _cache]


def invalidate_cache() -> None:
    global _cache
    _cache = []
