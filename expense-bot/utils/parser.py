class ParseError(Exception):
    pass

def parse_expense(text: str) -> dict:
    """Returns {amount: float, note: str} or raises ParseError."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        raise ParseError("No input provided.")
    try:
        amount = float(parts[0])
    except ValueError:
        raise ParseError(f"Expected a number first, got '{parts[0]}'.")
    if amount <= 0:
        raise ParseError("Amount must be a positive number.")
    note = parts[1].strip() if len(parts) > 1 else ""
    return {"amount": amount, "note": note}
