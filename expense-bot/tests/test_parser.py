import pytest
from utils.parser import parse_expense, ParseError

def test_amount_with_long_note():
    result = parse_expense("450 food lunch at zomato")
    assert result["amount"] == 450.0
    assert result["note"] == "food lunch at zomato"

def test_amount_with_short_note():
    result = parse_expense("450 zomato")
    assert result["amount"] == 450.0
    assert result["note"] == "zomato"

def test_amount_only():
    result = parse_expense("450")
    assert result["amount"] == 450.0
    assert result["note"] == ""

def test_decimal_amount():
    result = parse_expense("1299.50 netflix")
    assert result["amount"] == 1299.50
    assert result["note"] == "netflix"

def test_invalid_text_raises():
    with pytest.raises(ParseError):
        parse_expense("lunch zomato")

def test_zero_raises():
    with pytest.raises(ParseError):
        parse_expense("0 lunch")

def test_negative_raises():
    with pytest.raises(ParseError):
        parse_expense("-100 lunch")

def test_empty_raises():
    with pytest.raises(ParseError):
        parse_expense("")

def test_whitespace_stripped():
    result = parse_expense("  300  coffee  ")
    assert result["amount"] == 300.0
    assert result["note"] == "coffee"
