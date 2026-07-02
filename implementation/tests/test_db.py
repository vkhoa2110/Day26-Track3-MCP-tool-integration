from __future__ import annotations

import pytest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


@pytest.fixture()
def adapter(tmp_path):
    db_path = create_database(tmp_path / "lab.sqlite3", reset=True)
    return SQLiteAdapter(db_path)


def test_search_filters_ordering_and_pagination(adapter):
    result = adapter.search(
        "students",
        filters={"cohort": "A1"},
        columns=["name", "cohort", "score"],
        order_by="score",
        descending=True,
        limit=1,
    )

    assert result["count"] == 1
    assert result["rows"][0]["cohort"] == "A1"
    assert result["rows"][0]["score"] == 91.5


def test_search_supports_operator_filters(adapter):
    result = adapter.search(
        "students",
        filters=[{"column": "score", "op": "gte", "value": 90}],
        columns=["name", "score"],
        order_by="score",
        descending=True,
    )

    assert [row["name"] for row in result["rows"]] == ["Hanh Vo", "An Nguyen"]


def test_insert_returns_inserted_payload(adapter):
    result = adapter.insert(
        "students",
        {
            "name": "Lan Do",
            "cohort": "C3",
            "email": "lan.do@example.edu",
            "score": 82.5,
        },
    )

    assert result["inserted_id"] is not None
    assert result["row"]["name"] == "Lan Do"
    assert result["row"]["email"] == "lan.do@example.edu"


def test_aggregate_supports_grouped_average(adapter):
    result = adapter.aggregate("students", metric="avg", column="score", group_by="cohort")

    averages = {row["cohort"]: row["value"] for row in result["rows"]}
    assert averages["A1"] == pytest.approx(87.75)
    assert averages["C3"] == pytest.approx(95.0)


def test_count_aggregate_does_not_require_column(adapter):
    result = adapter.aggregate("students", metric="count")

    assert result["rows"] == [{"value": 5}]


@pytest.mark.parametrize(
    ("callable_name", "args", "message"),
    [
        ("search", ("missing",), "unknown table"),
        ("search", ("students", ["not_a_column"]), "unknown column"),
        ("search", ("students", None, {"score": {"op": "between", "value": [80, 90]}}), "unsupported filter"),
        ("insert", ("students", {}), "cannot be empty"),
        ("aggregate", ("students", "median", "score"), "unsupported aggregate"),
        ("aggregate", ("students", "avg", "name"), "numeric column"),
    ],
)
def test_invalid_requests_are_rejected(adapter, callable_name, args, message):
    method = getattr(adapter, callable_name)

    with pytest.raises(ValidationError, match=message):
        if callable_name == "search" and len(args) == 2:
            method(args[0], columns=args[1])
        elif callable_name == "search" and len(args) == 3:
            method(args[0], columns=args[1], filters=args[2])
        else:
            method(*args)
