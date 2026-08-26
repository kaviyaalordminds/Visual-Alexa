"""docs/phase-2/FILESYSTEM-CONTROL.md — real filesystem operations
against a real temp sandbox. No `delete` method exists on FilesystemEngine
at all (docs/phase-2 §7) — this is verified by test_no_delete_method_exists
rather than merely "no delete tool is registered."
"""

import tempfile
from pathlib import Path

import pytest
from computer_control.filesystem import FilesystemEngine, PathValidator, default_policy
from computer_control.filesystem.engine import FilesystemError
from computer_control.filesystem.models import SearchCriteria


@pytest.fixture
def sandbox():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def engine(sandbox):
    return FilesystemEngine(PathValidator(default_policy([sandbox])))


async def test_create_folder_and_list_directory(engine, sandbox):
    folder = await engine.create_folder(str(sandbox), "Projects")
    assert folder.is_directory is True

    entries = await engine.list_directory(str(sandbox))
    assert [e.name for e in entries] == ["Projects"]


async def test_create_file_then_get_metadata(engine, sandbox):
    created = await engine.create_file(str(sandbox), "notes.txt", "hello")
    assert created.size_bytes == 5

    metadata = await engine.get_metadata(created.path)
    assert metadata.name == "notes.txt"
    assert metadata.extension == ".txt"


async def test_rename_moves_the_file_and_old_name_is_gone(engine, sandbox):
    created = await engine.create_file(str(sandbox), "test.txt", "hi")
    renamed = await engine.rename(created.path, "veyra-test.txt")
    assert renamed.name == "veyra-test.txt"
    with pytest.raises(FilesystemError):
        await engine.get_metadata(created.path)


async def test_search_finds_by_filename_and_extension(engine, sandbox):
    await engine.create_file(str(sandbox), "veyra-test.txt", "x")
    await engine.create_file(str(sandbox), "other.pdf", "x")

    matches = await engine.search(SearchCriteria(directory=str(sandbox), filename_contains="veyra"))
    assert [m.name for m in matches] == ["veyra-test.txt"]

    pdf_matches = await engine.search(SearchCriteria(directory=str(sandbox), extension=".pdf"))
    assert [m.name for m in pdf_matches] == ["other.pdf"]


async def test_search_is_bounded_by_max_results(engine, sandbox):
    for i in range(10):
        await engine.create_file(str(sandbox), f"file{i}.txt", "x")
    matches = await engine.search(SearchCriteria(directory=str(sandbox), max_results=3))
    assert len(matches) == 3


async def test_copy_creates_a_second_independent_file(engine, sandbox):
    created = await engine.create_file(str(sandbox), "a.txt", "hi")
    copied = await engine.copy(created.path, str(sandbox / "b.txt"))
    assert copied.path != created.path
    # original still exists
    await engine.get_metadata(created.path)


async def test_move_relocates_the_file(engine, sandbox):
    (sandbox / "sub").mkdir()
    created = await engine.create_file(str(sandbox), "a.txt", "hi")
    moved = await engine.move(created.path, str(sandbox / "sub" / "a.txt"))
    assert moved.path.endswith("sub/a.txt") or moved.path.endswith("sub\\a.txt")


async def test_create_folder_rejects_path_separators_in_name(engine, sandbox):
    with pytest.raises(FilesystemError):
        await engine.create_folder(str(sandbox), "../escape")


async def test_create_folder_rejects_existing_target(engine, sandbox):
    await engine.create_folder(str(sandbox), "Projects")
    with pytest.raises(FilesystemError):
        await engine.create_folder(str(sandbox), "Projects")


async def test_get_metadata_on_missing_file_raises(engine, sandbox):
    with pytest.raises(FilesystemError):
        await engine.get_metadata(str(sandbox / "does-not-exist.txt"))


def test_no_delete_method_exists_on_the_engine():
    assert not hasattr(FilesystemEngine, "delete")
