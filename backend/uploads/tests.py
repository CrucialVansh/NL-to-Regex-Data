import csv
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from uploads.excel_reader import get_excel_data_address, get_excel_sheet_names
from uploads.services import (
    ColumnValidationError,
    get_file_columns,
    is_allowed_upload,
    validate_target_columns,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_XLSX = PROJECT_ROOT / "test.xlsx"


class UploadServiceTests(SimpleTestCase):
    def test_allowed_extensions(self):
        self.assertTrue(is_allowed_upload("data.csv"))
        self.assertTrue(is_allowed_upload("data.xlsx"))
        self.assertFalse(is_allowed_upload("data.xls"))
        self.assertFalse(is_allowed_upload("data.exe"))

    def test_csv_column_extraction(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ID", "Email"])
            path = handle.name

        try:
            columns = get_file_columns(path)
        finally:
            Path(path).unlink(missing_ok=True)

        self.assertEqual(columns, ["ID", "Email"])

    def test_validate_target_columns(self):
        normalized = validate_target_columns(["email"], ["ID", "Email"])
        self.assertEqual(normalized, ["Email"])

    def test_missing_columns_raise(self):
        with self.assertRaises(ColumnValidationError):
            validate_target_columns(["Missing"], ["ID", "Email"])

    def test_excel_column_extraction_for_nonstandard_workbook(self):
        if not TEST_XLSX.is_file():
            self.skipTest("test.xlsx fixture not available")

        columns = get_file_columns(str(TEST_XLSX))
        self.assertEqual(columns, ["id", "name", "email"])
        self.assertEqual(get_excel_sheet_names(str(TEST_XLSX)), ["test"])
        self.assertEqual(get_excel_data_address(str(TEST_XLSX)), "'test'!A1")

    def test_excel_row_export_for_nonstandard_workbook(self):
        if not TEST_XLSX.is_file():
            self.skipTest("test.xlsx fixture not available")

        from uploads.excel_reader import read_excel_rows

        rows = read_excel_rows(str(TEST_XLSX))
        self.assertEqual(rows[0], ["id", "name", "email"])
        self.assertEqual(len(rows), 4)
