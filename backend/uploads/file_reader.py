"""Paginated reader for original uploaded CSV and Excel files."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pyarrow.csv as pcsv

from .excel_reader import read_excel_rows


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _paginate_csv(local_path: str, page: int, page_size: int) -> dict[str, Any]:
    table = pcsv.read_csv(local_path)
    total_rows = table.num_rows
    columns = table.schema.names

    if total_rows == 0:
        return {"columns": columns, "rows": [], "total_rows": 0, "total_pages": 0}

    offset = (page - 1) * page_size
    sliced = table.slice(offset, page_size)
    pydict = sliced.to_pydict()
    rows = [
        {col: _json_safe(pydict[col][i]) for col in columns}
        for i in range(sliced.num_rows)
    ]
    return {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "total_pages": math.ceil(total_rows / page_size),
    }


def _paginate_excel(local_path: str, page: int, page_size: int) -> dict[str, Any]:
    all_rows = read_excel_rows(local_path)
    if not all_rows:
        return {"columns": [], "rows": [], "total_rows": 0, "total_pages": 0}

    columns = all_rows[0]
    data_rows = all_rows[1:]
    total_rows = len(data_rows)

    if total_rows == 0:
        return {"columns": columns, "rows": [], "total_rows": 0, "total_pages": 0}

    offset = (page - 1) * page_size
    page_rows = data_rows[offset : offset + page_size]
    rows = [
        {col: _json_safe(val) for col, val in zip(columns, row)}
        for row in page_rows
    ]
    return {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "total_pages": math.ceil(total_rows / page_size),
    }


def paginate_uploaded_file(file_path: str, page: int, page_size: int) -> dict[str, Any]:
    """Return one page of rows from an uploaded CSV or Excel file."""
    lower = file_path.lower()
    if lower.endswith(".csv"):
        return _paginate_csv(file_path, page, page_size)
    if lower.endswith(".xlsx"):
        return _paginate_excel(file_path, page, page_size)
    raise ValueError(f"Unsupported file type for preview: {file_path}")
