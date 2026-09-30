"""Cursor pagination, 20 per page by default (CLAUDE.md section 6.5).

Cursors stay correct while new rows arrive (new orders at the counter), unlike
page numbers, which skip or repeat items.
"""

from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"
