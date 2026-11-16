from __future__ import annotations

import os


MAX_EXPENSES = 20

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# The HTML templates are kept in the project root, next to main.py.
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
