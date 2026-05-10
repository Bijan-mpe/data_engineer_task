"""Pagination helpers shared by repository list methods."""

from __future__ import annotations

MAX_PAGE_LIMIT = 500


def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Validate limit/offset values and return them unchanged when valid."""
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
    if limit > MAX_PAGE_LIMIT:
        raise ValueError(f"limit must be less than or equal to {MAX_PAGE_LIMIT}")
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    return limit, offset
