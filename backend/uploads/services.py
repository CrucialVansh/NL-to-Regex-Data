"""File validation helpers for uploads and job column selection."""

import csv
import logging
import os
from pathlib import Path

import pyarrow.parquet as pq
from django.conf import settings

from nltoregex.cache_utils import get_cached_file_columns, set_cached_file_columns
from uploads.excel_reader import ExcelReadError, read_excel_columns

logger = logging.getLogger(__name__)


class ColumnValidationError(ValueError):
    pass


def is_allowed_upload(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in settings.ALLOWED_UPLOAD_EXTENSIONS


def _read_csv_columns(file_path: str) -> list[str]:
    with open(file_path, newline="", encoding="utf-8-sig") as handle:
        return next(csv.reader(handle))


def _read_excel_columns(file_path: str) -> list[str]:
    try:
        return read_excel_columns(file_path)
    except ExcelReadError as exc:
        raise ValueError(str(exc)) from exc


def _read_columns_from_file(file_path: str) -> list[str]:
    lower_path = file_path.lower()
    if lower_path.endswith(".csv"):
        return _read_csv_columns(file_path)

    if lower_path.endswith(".xlsx"):
        return _read_excel_columns(file_path)

    if lower_path.endswith(".parquet") or os.path.isdir(file_path):
        schema_path = file_path
        if os.path.isdir(file_path):
            schema_path = os.path.join(file_path, os.listdir(file_path)[0])
        return pq.read_schema(schema_path).names

    raise ValueError(f"Unsupported file type for column validation: {file_path}")


def get_file_columns(file_path: str, uploaded_file_id: str | None = None) -> list[str]:
    """Read header columns from CSV, Excel, or Parquet with optional Redis caching."""
    if not file_path or not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_mtime = os.path.getmtime(file_path)
    if uploaded_file_id:
        cached_columns = get_cached_file_columns(uploaded_file_id, file_mtime)
        if cached_columns is not None:
            logger.debug("Cache hit for file columns: uploaded_file_id=%s", uploaded_file_id)
            return cached_columns

    columns = _read_columns_from_file(file_path)
    columns = [column for column in columns if column]

    if uploaded_file_id:
        set_cached_file_columns(uploaded_file_id, file_mtime, columns)
        logger.debug("Cached file columns: uploaded_file_id=%s", uploaded_file_id)

    return columns


def validate_target_columns(
    target_columns: list[str],
    available_columns: list[str],
) -> list[str]:
    """Match requested columns to the file schema and return canonical column names."""
    if not target_columns:
        raise ColumnValidationError("At least one target column is required")

    lookup = {column.lower(): column for column in available_columns}
    normalized_columns = []
    missing_columns = []

    for column in target_columns:
        if not isinstance(column, str) or not column.strip():
            raise ColumnValidationError("Each target column must be a non-empty string")
        actual_column = lookup.get(column.strip().lower())
        if actual_column is None:
            missing_columns.append(column)
        else:
            normalized_columns.append(actual_column)

    if missing_columns:
        raise ColumnValidationError(
            f"Columns not found in uploaded file: {missing_columns}. "
            f"Available columns: {available_columns}"
        )

    return normalized_columns
