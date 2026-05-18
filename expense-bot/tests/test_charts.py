import pytest
from io import BytesIO
from utils.charts import generate_pie_chart

def test_returns_bytesio():
    data = {"Food": 5000.0, "Transport": 2000.0, "Shopping": 3000.0}
    result = generate_pie_chart(data, "May 2026")
    assert isinstance(result, BytesIO)

def test_bytesio_is_valid_png():
    data = {"Food": 5000.0}
    result = generate_pie_chart(data, "May 2026")
    result.seek(0)
    header = result.read(8)
    assert header == b"\x89PNG\r\n\x1a\n"

def test_single_category():
    data = {"Food": 10000.0}
    result = generate_pie_chart(data, "May 2026")
    assert len(result.getvalue()) > 0

def test_empty_data_raises():
    with pytest.raises(ValueError):
        generate_pie_chart({}, "May 2026")
