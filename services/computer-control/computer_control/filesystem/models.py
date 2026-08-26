"""Filesystem-specific models. docs/phase-2/FILESYSTEM-CONTROL.md."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FileMetadata(BaseModel):
    path: str
    name: str
    is_directory: bool
    size_bytes: int | None = None
    extension: str | None = None
    modified_at: datetime | None = None
    created_at: datetime | None = None


class SearchCriteria(BaseModel):
    """docs/phase-2 §7.1 — a search is always scoped to a directory the
    caller names (which must itself resolve inside an allowed root); there
    is no 'search the whole disk' default."""

    directory: str
    filename_contains: str | None = None
    extension: str | None = None
    modified_after: datetime | None = None
    modified_before: datetime | None = None
    min_size_bytes: int | None = None
    max_size_bytes: int | None = None
    recursive: bool = True
    max_results: int = 200
