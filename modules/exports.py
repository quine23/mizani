"""Module 8 (part): export a user's transactions to CSV or Excel."""
import csv
import io

from modules.errors import FinanceError
from modules.formatting import CURRENCY

HEADERS = ["Date", "Type", "Category", "Description", f"Amount ({CURRENCY})"]


def _safe_text(value):
    """Stop spreadsheet programs from running a description that starts like a formula."""
    text = str(value or "")
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _rows(transactions):
    return [[t.transaction_date, t.label, t.category_name, _safe_text(t.description), t.amount]
            for t in transactions]


def export_csv(transactions):
    """Return the CSV file content as text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)
    for row in _rows(transactions):
        row[-1] = f"{row[-1]:.2f}"
        writer.writerow(row)
    return buffer.getvalue()


def export_excel(transactions):
    """Return an .xlsx file as bytes."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        raise FinanceError("Excel export needs the openpyxl package. Run: pip install openpyxl") from None

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Transactions"
    sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in _rows(transactions):
        sheet.append(row)
    for cell in sheet["E"][1:]:
        cell.number_format = "#,##0.00"
    for column, width in zip("ABCDE", (12, 10, 20, 44, 16)):
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
