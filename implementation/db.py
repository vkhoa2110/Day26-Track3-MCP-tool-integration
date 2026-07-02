from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    """Small SQLite data-access layer with identifier validation."""

    SUPPORTED_FILTER_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "like", "in", "is_null"}
    SUPPORTED_AGGREGATES = {"count", "avg", "sum", "min", "max"}
    NUMERIC_TYPE_MARKERS = {"INT", "REAL", "NUM", "DEC", "DOUB", "FLOA"}

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        table = self._validate_table(table)
        quoted_table = self._quote_identifier(table)

        with self.connect() as conn:
            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not bool(row["notnull"]) and not bool(row["pk"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
            ]
            foreign_keys = [
                {
                    "column": row["from"],
                    "references_table": row["table"],
                    "references_column": row["to"],
                    "on_update": row["on_update"],
                    "on_delete": row["on_delete"],
                }
                for row in conn.execute(f"PRAGMA foreign_key_list({quoted_table})").fetchall()
            ]

        return {"table": table, "columns": columns, "foreign_keys": foreign_keys}

    def get_database_schema(self) -> dict[str, Any]:
        return {"tables": [self.get_table_schema(table) for table in self.list_tables()]}

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table = self._validate_table(table)
        selected_columns = self._validate_selected_columns(table, columns)
        limit = self._validate_limit(limit)
        offset = self._validate_offset(offset)

        where_sql, params = self._build_where(table, filters)
        order_sql = ""
        if order_by is not None:
            order_column = self._validate_column(table, order_by)
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {self._quote_identifier(order_column)} {direction}"

        column_sql = ", ".join(self._quote_identifier(column) for column in selected_columns)
        table_sql = self._quote_identifier(table)
        sql = f"SELECT {column_sql} FROM {table_sql}{where_sql}{order_sql} LIMIT ? OFFSET ?"
        query_params = [*params, limit, offset]

        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, query_params).fetchall()]

        return {
            "table": table,
            "columns": selected_columns,
            "limit": limit,
            "offset": offset,
            "count": len(rows),
            "rows": rows,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table = self._validate_table(table)
        if not isinstance(values, dict):
            raise ValidationError("values must be an object")
        if not values:
            raise ValidationError("insert values cannot be empty")

        columns = [self._validate_column(table, column) for column in values.keys()]
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(self._quote_identifier(column) for column in columns)
        table_sql = self._quote_identifier(table)
        sql = f"INSERT INTO {table_sql} ({column_sql}) VALUES ({placeholders})"

        try:
            with self.connect() as conn:
                cursor = conn.execute(sql, [values[column] for column in columns])
                inserted_id = cursor.lastrowid
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"insert failed integrity check: {exc}") from exc
        except sqlite3.Error as exc:
            raise ValidationError(f"insert failed: {exc}") from exc

        inserted_row = self._fetch_inserted_row(table, inserted_id, values)
        return {"table": table, "inserted_id": inserted_id, "row": inserted_row}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        table = self._validate_table(table)
        metric = self._validate_metric(metric)
        group_columns = self._validate_group_by(table, group_by)

        aggregate_sql = self._build_aggregate_expression(table, metric, column)
        select_parts = [self._quote_identifier(column_name) for column_name in group_columns]
        select_parts.append(f"{aggregate_sql} AS value")

        table_sql = self._quote_identifier(table)
        where_sql, params = self._build_where(table, filters)
        group_sql = ""
        if group_columns:
            group_sql = " GROUP BY " + ", ".join(self._quote_identifier(column_name) for column_name in group_columns)

        sql = f"SELECT {', '.join(select_parts)} FROM {table_sql}{where_sql}{group_sql}"

        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_columns,
            "count": len(rows),
            "rows": rows,
        }

    def _fetch_inserted_row(self, table: str, inserted_id: int | None, values: dict[str, Any]) -> dict[str, Any]:
        columns = self._columns_for_table(table)
        if inserted_id is not None and "id" in columns:
            result = self.search(table, filters={"id": inserted_id}, limit=1)
            if result["rows"]:
                return result["rows"][0]
        return dict(values)

    def _validate_table(self, table: str) -> str:
        if not isinstance(table, str) or not table:
            raise ValidationError("table must be a non-empty string")
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"unknown table '{table}'. Valid tables: {', '.join(tables)}")
        return table

    def _columns_for_table(self, table: str) -> dict[str, dict[str, Any]]:
        quoted_table = self._quote_identifier(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
        return {
            row["name"]: {
                "type": row["type"],
                "nullable": not bool(row["notnull"]),
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        }

    def _validate_column(self, table: str, column: str) -> str:
        if not isinstance(column, str) or not column:
            raise ValidationError("column must be a non-empty string")
        columns = self._columns_for_table(table)
        if column not in columns:
            valid = ", ".join(columns)
            raise ValidationError(f"unknown column '{column}' for table '{table}'. Valid columns: {valid}")
        return column

    def _validate_selected_columns(self, table: str, columns: list[str] | None) -> list[str]:
        all_columns = list(self._columns_for_table(table))
        if columns is None:
            return all_columns
        if not isinstance(columns, list) or not columns:
            raise ValidationError("columns must be a non-empty list when provided")
        return [self._validate_column(table, column) for column in columns]

    def _validate_limit(self, limit: int) -> int:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValidationError("limit must be an integer")
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be between 1 and 100")
        return limit

    def _validate_offset(self, offset: int) -> int:
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise ValidationError("offset must be an integer")
        if offset < 0:
            raise ValidationError("offset cannot be negative")
        return offset

    def _validate_metric(self, metric: str) -> str:
        if not isinstance(metric, str) or not metric:
            raise ValidationError("metric must be a non-empty string")
        normalized = metric.lower()
        if normalized not in self.SUPPORTED_AGGREGATES:
            valid = ", ".join(sorted(self.SUPPORTED_AGGREGATES))
            raise ValidationError(f"unsupported aggregate metric '{metric}'. Valid metrics: {valid}")
        return normalized

    def _validate_group_by(self, table: str, group_by: str | list[str] | None) -> list[str]:
        if group_by is None:
            return []
        if isinstance(group_by, str):
            return [self._validate_column(table, group_by)]
        if isinstance(group_by, list) and group_by:
            return [self._validate_column(table, column) for column in group_by]
        raise ValidationError("group_by must be a column name or a non-empty list of column names")

    def _build_aggregate_expression(self, table: str, metric: str, column: str | None) -> str:
        sql_metric = metric.upper()
        if metric == "count" and column is None:
            return "COUNT(*)"

        if column is None:
            raise ValidationError(f"aggregate metric '{metric}' requires a column")

        column = self._validate_column(table, column)
        if metric in {"avg", "sum"} and not self._is_numeric_column(table, column):
            raise ValidationError(f"aggregate metric '{metric}' requires a numeric column")

        return f"{sql_metric}({self._quote_identifier(column)})"

    def _is_numeric_column(self, table: str, column: str) -> bool:
        column_type = self._columns_for_table(table)[column]["type"].upper()
        return any(marker in column_type for marker in self.NUMERIC_TYPE_MARKERS)

    def _build_where(
        self,
        table: str,
        filters: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> tuple[str, list[Any]]:
        normalized_filters = self._normalize_filters(filters)
        if not normalized_filters:
            return "", []

        conditions: list[str] = []
        params: list[Any] = []
        for item in normalized_filters:
            column = self._validate_column(table, item["column"])
            operator = item["op"].lower()
            if operator not in self.SUPPORTED_FILTER_OPERATORS:
                valid = ", ".join(sorted(self.SUPPORTED_FILTER_OPERATORS))
                raise ValidationError(f"unsupported filter operator '{item['op']}'. Valid operators: {valid}")

            quoted_column = self._quote_identifier(column)
            value = item.get("value")

            if operator == "eq":
                conditions.append(f"{quoted_column} = ?")
                params.append(value)
            elif operator == "ne":
                conditions.append(f"{quoted_column} != ?")
                params.append(value)
            elif operator == "gt":
                conditions.append(f"{quoted_column} > ?")
                params.append(value)
            elif operator == "gte":
                conditions.append(f"{quoted_column} >= ?")
                params.append(value)
            elif operator == "lt":
                conditions.append(f"{quoted_column} < ?")
                params.append(value)
            elif operator == "lte":
                conditions.append(f"{quoted_column} <= ?")
                params.append(value)
            elif operator == "like":
                conditions.append(f"{quoted_column} LIKE ?")
                params.append(value)
            elif operator == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("'in' filter value must be a non-empty list")
                placeholders = ", ".join("?" for _ in value)
                conditions.append(f"{quoted_column} IN ({placeholders})")
                params.extend(value)
            elif operator == "is_null":
                if not isinstance(value, bool):
                    raise ValidationError("'is_null' filter value must be true or false")
                conditions.append(f"{quoted_column} IS {'NULL' if value else 'NOT NULL'}")

        return " WHERE " + " AND ".join(conditions), params

    def _normalize_filters(
        self,
        filters: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if filters is None:
            return []
        if isinstance(filters, list):
            normalized = []
            for item in filters:
                if not isinstance(item, dict):
                    raise ValidationError("each filter must be an object")
                if "column" not in item:
                    raise ValidationError("each filter object must include a column")
                normalized.append(
                    {
                        "column": item["column"],
                        "op": item.get("op", "eq"),
                        "value": item.get("value"),
                    }
                )
            return normalized
        if isinstance(filters, dict):
            normalized = []
            for column, raw_condition in filters.items():
                if isinstance(raw_condition, dict):
                    if "op" in raw_condition:
                        normalized.append(
                            {
                                "column": column,
                                "op": raw_condition["op"],
                                "value": raw_condition.get("value"),
                            }
                        )
                    elif len(raw_condition) == 1:
                        op, value = next(iter(raw_condition.items()))
                        normalized.append({"column": column, "op": op, "value": value})
                    else:
                        raise ValidationError(f"filter for column '{column}' must include op/value")
                else:
                    normalized.append({"column": column, "op": "eq", "value": raw_condition})
            return normalized
        raise ValidationError("filters must be an object, a list of objects, or null")

    def _quote_identifier(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'
