"""Paginate Spark job output stored as Parquet without loading the full file."""

import logging
import math
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pyarrow as pa
import pyarrow.dataset as ds

from nltoregex.cache_utils import get_cached_result_page, set_cached_result_page

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Convert Arrow/Python values into JSON-serializable forms."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _batch_to_records(batch: pa.RecordBatch) -> list[dict[str, Any]]:
    columns = batch.to_pydict()
    if not columns:
        return []

    column_names = list(columns.keys())
    row_count = batch.num_rows
    return [
        {
            column: _json_safe(columns[column][row_index])
            for column in column_names
        }
        for row_index in range(row_count)
    ]


def _paginate_parquet(result_path: str, page: int, page_size: int) -> dict[str, Any]:
    """Scan Parquet in batches until the requested page window is filled."""
    dataset = ds.dataset(result_path, format="parquet")
    total_rows = dataset.count_rows()
    columns = dataset.schema.names

    if total_rows == 0:
        return {
            "columns": columns,
            "rows": [],
            "total_rows": 0,
            "total_pages": 0,
        }

    offset = (page - 1) * page_size
    if offset >= total_rows:
        return {
            "columns": columns,
            "rows": [],
            "total_rows": total_rows,
            "total_pages": math.ceil(total_rows / page_size),
        }

    rows_to_collect = min(page_size, total_rows - offset)
    collected_rows: list[dict[str, Any]] = []
    skipped_rows = 0

    scanner = dataset.scanner(batch_size=min(8192, page_size))
    for batch in scanner.to_batches():
        batch_row_count = batch.num_rows

        if skipped_rows + batch_row_count <= offset:
            skipped_rows += batch_row_count
            continue

        start_in_batch = max(0, offset - skipped_rows)
        remaining = rows_to_collect - len(collected_rows)
        slice_length = min(batch_row_count - start_in_batch, remaining)
        sliced_batch = batch.slice(start_in_batch, slice_length)
        collected_rows.extend(_batch_to_records(sliced_batch))
        skipped_rows += batch_row_count

        if len(collected_rows) >= rows_to_collect:
            break

    return {
        "columns": columns,
        "rows": collected_rows,
        "total_rows": total_rows,
        "total_pages": math.ceil(total_rows / page_size),
    }


def paginate_parquet_result(
    result_path: str,
    page: int,
    page_size: int,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not result_path or not os.path.exists(result_path):
        raise FileNotFoundError(f"Result path not found: {result_path}")

    if job_id:
        cached_page = get_cached_result_page(job_id, page, page_size)
        if cached_page is not None:
            logger.debug("Cache hit for result page: job_id=%s page=%s", job_id, page)
            return cached_page

    page_data = _paginate_parquet(result_path, page, page_size)

    if job_id:
        set_cached_result_page(job_id, page, page_size, page_data)
        logger.debug("Cached result page: job_id=%s page=%s", job_id, page)

    return page_data
