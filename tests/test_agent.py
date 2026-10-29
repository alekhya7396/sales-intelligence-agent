import pytest
from database import initialize_database
from agent import answer_question


@pytest.fixture(autouse=True)
def reload_db():
    initialize_database()


def test_total_revenue_returns_numeric_supporting_data():
    result = answer_question("What is the total revenue?")
    assert result["ok"] is True
    assert result["intent"] == "total_revenue"
    assert result["data"][0]["total_revenue"] > 0
    assert result["data"][0]["valid_transactions"] == 48


def test_top_product_has_ranked_rows():
    result = answer_question("Which product generated the highest revenue?")
    assert result["ok"] is True
    assert result["data"][0]["Product"] == "Monitor"
    assert result["data"][0]["total_revenue"] > 0


def test_monthly_trend_has_six_months():
    result = answer_question("What is the monthly revenue trend?")
    assert result["ok"] is True
    assert len(result["data"]) == 6
    assert result["data"][0]["month"] == "2026-01"


def test_region_query_returns_ranked_regions():
    result = answer_question("Which region generated the highest sales?")
    assert result["ok"] is True
    assert result["data"][0]["Region"] in {"North", "South", "East", "West"}
    assert len(result["data"]) == 4


def test_month_comparison_returns_change():
    result = answer_question("How did revenue change between March and April?")
    assert result["ok"] is True
    assert result["intent"] == "month_comparison"
    assert "change" in result["data"][-1]


def test_unsupported_question_does_not_execute_sql():
    result = answer_question("What is the weather tomorrow?")
    assert result["ok"] is False
    assert result["sql"] is None


def test_blank_question_is_rejected():
    with pytest.raises(ValueError):
        answer_question("   ")
