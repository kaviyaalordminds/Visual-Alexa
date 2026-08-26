"""Filesystem engine. docs/phase-2/FILESYSTEM-CONTROL.md.

Every method validates every path it touches via PathValidator before any
real filesystem call — see docs/phase-2 §7.2. Deletion is intentionally
not implemented (docs/phase-2 §7, brief §7): there is no `delete` method
on this class at all, so there is no code path that could accidentally
wire a delete tool up to it.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from veyra_contracts import ErrorCategory

from computer_control.filesystem.models import FileMetadata, SearchCriteria
from computer_control.filesystem.path_policy import PathValidator

_INVALID_NAME_CHARS = set('/\\:*?"<>|')


class FilesystemError(ValueError):
    def __init__(self, code: ErrorCategory, message: str) -> None:
        super().__init__(message)
        self.code = code


def _validate_simple_name(name: str) -> None:
    """A file/folder *name* (not a path) must not contain path separators
    or traversal segments — this is what stops 'name=../../evil' from
    escaping the validated parent directory."""
    if not name or name in (".", "..") or any(c in _INVALID_NAME_CHARS for c in name):
        raise FilesystemError(
            ErrorCategory.VALIDATION_ERROR, f"'{name}' is not a valid file/folder name."
        )


def _stat_to_metadata(path: Path) -> FileMetadata:
    stat = path.stat()
    return FileMetadata(
        path=str(path),
        name=path.name,
        is_directory=path.is_dir(),
        size_bytes=None if path.is_dir() else stat.st_size,
        extension=path.suffix or None,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        created_at=datetime.fromtimestamp(stat.st_ctime, tz=UTC),
    )


class FilesystemEngine:
    def __init__(self, validator: PathValidator) -> None:
        self._validator = validator

    async def get_metadata(self, path: str) -> FileMetadata:
        resolved = self._validator.validate(path)
        return await asyncio.to_thread(self._get_metadata_sync, resolved)

    def _get_metadata_sync(self, resolved: Path) -> FileMetadata:
        if not resolved.exists():
            raise FilesystemError(ErrorCategory.FILE_NOT_FOUND, f"'{resolved}' does not exist.")
        return _stat_to_metadata(resolved)

    async def list_directory(self, directory: str) -> list[FileMetadata]:
        resolved = self._validator.validate(directory)
        return await asyncio.to_thread(self._list_directory_sync, resolved)

    def _list_directory_sync(self, resolved: Path) -> list[FileMetadata]:
        if not resolved.is_dir():
            raise FilesystemError(
                ErrorCategory.FILE_NOT_FOUND, f"'{resolved}' is not a directory."
            )
        return [_stat_to_metadata(child) for child in sorted(resolved.iterdir())]

    async def search(self, criteria: SearchCriteria) -> list[FileMetadata]:
        resolved_dir = self._validator.validate(criteria.directory)
        return await asyncio.to_thread(self._search_sync, resolved_dir, criteria)

    def _search_sync(self, resolved_dir: Path, criteria: SearchCriteria) -> list[FileMetadata]:
        if not resolved_dir.is_dir():
            raise FilesystemError(
                ErrorCategory.FILE_NOT_FOUND, f"'{resolved_dir}' is not a directory."
            )
        iterator = resolved_dir.rglob("*") if criteria.recursive else resolved_dir.glob("*")
        results: list[FileMetadata] = []
        for candidate in iterator:
            if len(results) >= criteria.max_results:
                break
            if (
                criteria.filename_contains
                and criteria.filename_contains.lower() not in candidate.name.lower()
            ):
                continue
            if criteria.extension and candidate.suffix.lower() != criteria.extension.lower():
                continue
            try:
                metadata = _stat_to_metadata(candidate)
            except OSError:
                continue
            if criteria.min_size_bytes is not None and (
                metadata.size_bytes is None or metadata.size_bytes < criteria.min_size_bytes
            ):
                continue
            if criteria.max_size_bytes is not None and (
                metadata.size_bytes is None or metadata.size_bytes > criteria.max_size_bytes
            ):
                continue
            if criteria.modified_after is not None and (
                metadata.modified_at is None or metadata.modified_at < criteria.modified_after
            ):
                continue
            if criteria.modified_before is not None and (
                metadata.modified_at is None or metadata.modified_at > criteria.modified_before
            ):
                continue
            results.append(metadata)
        return results

    async def create_folder(self, parent: str, name: str) -> FileMetadata:
        _validate_simple_name(name)
        resolved_parent = self._validator.validate(parent)
        target = self._validator.validate(str(resolved_parent / name))
        return await asyncio.to_thread(self._create_folder_sync, target)

    def _create_folder_sync(self, target: Path) -> FileMetadata:
        if target.exists():
            raise FilesystemError(
                ErrorCategory.VALIDATION_ERROR, f"'{target}' already exists."
            )
        target.mkdir(parents=False)
        return _stat_to_metadata(target)

    async def create_file(self, parent: str, name: str, content: str = "") -> FileMetadata:
        _validate_simple_name(name)
        resolved_parent = self._validator.validate(parent)
        target = self._validator.validate(str(resolved_parent / name))
        return await asyncio.to_thread(self._create_file_sync, target, content)

    def _create_file_sync(self, target: Path, content: str) -> FileMetadata:
        if target.exists():
            raise FilesystemError(
                ErrorCategory.VALIDATION_ERROR, f"'{target}' already exists."
            )
        target.write_text(content, encoding="utf-8")
        return _stat_to_metadata(target)

    async def copy(self, source: str, destination: str) -> FileMetadata:
        resolved_source = self._validator.validate(source)
        resolved_dest = self._validator.validate(destination)
        return await asyncio.to_thread(self._copy_sync, resolved_source, resolved_dest)

    def _copy_sync(self, source: Path, destination: Path) -> FileMetadata:
        if not source.exists():
            raise FilesystemError(ErrorCategory.FILE_NOT_FOUND, f"'{source}' does not exist.")
        if destination.exists():
            raise FilesystemError(
                ErrorCategory.VALIDATION_ERROR, f"'{destination}' already exists."
            )
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return _stat_to_metadata(destination)

    async def move(self, source: str, destination: str) -> FileMetadata:
        resolved_source = self._validator.validate(source)
        resolved_dest = self._validator.validate(destination)
        return await asyncio.to_thread(self._move_sync, resolved_source, resolved_dest)

    def _move_sync(self, source: Path, destination: Path) -> FileMetadata:
        if not source.exists():
            raise FilesystemError(ErrorCategory.FILE_NOT_FOUND, f"'{source}' does not exist.")
        if destination.exists():
            raise FilesystemError(
                ErrorCategory.VALIDATION_ERROR, f"'{destination}' already exists."
            )
        shutil.move(str(source), str(destination))
        return _stat_to_metadata(destination)

    async def rename(self, path: str, new_name: str) -> FileMetadata:
        _validate_simple_name(new_name)
        resolved = self._validator.validate(path)
        target = self._validator.validate(str(resolved.parent / new_name))
        return await asyncio.to_thread(self._move_sync, resolved, target)

    async def open_file(
        self, path: str, launcher: Callable[[Path], None]
    ) -> None:
        """`launcher` is injected so the platform-specific "open with the
        associated application" mechanism (os.startfile on Windows) stays
        out of this platform-independent engine — see
        docs/phase-2/FILESYSTEM-CONTROL.md §7.3 and
        computer_control.windows.filesystem_launcher for the real one."""
        resolved = self._validator.validate(path)

        def _open() -> None:
            if not resolved.exists():
                raise FilesystemError(
                    ErrorCategory.FILE_NOT_FOUND, f"'{resolved}' does not exist."
                )
            launcher(resolved)

        await asyncio.to_thread(_open)
