"""docs/phase-2/FILESYSTEM-CONTROL.md §7.2 — path traversal, protected
paths, UNC/network-share rejection. This is the highest-value security
test in the whole Phase 2 suite: it runs against a real filesystem, in
this environment, for real.
"""

import tempfile
from pathlib import Path

import pytest
from computer_control.filesystem import (
    PathNotAllowedError,
    PathProtectedError,
    PathValidator,
    default_policy,
)
from computer_control.filesystem.path_policy import PathPolicy


@pytest.fixture
def sandbox():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def validator(sandbox):
    return PathValidator(default_policy([sandbox]))


def test_path_inside_allowed_root_is_valid(validator, sandbox):
    result = validator.validate(str(sandbox / "sub" / "file.txt"))
    assert result == (sandbox / "sub" / "file.txt").resolve()


def test_traversal_outside_allowed_root_is_denied(validator, sandbox):
    with pytest.raises((PathNotAllowedError, PathProtectedError)):
        validator.validate(str(sandbox) + "/../../etc/passwd")


def test_path_outside_any_allowed_root_is_denied(validator):
    with pytest.raises(PathNotAllowedError):
        validator.validate("/some/totally/unrelated/path.txt")


@pytest.mark.parametrize(
    "protected",
    ["/etc/passwd", "/bin/bash", "/usr/lib/foo", "/root/.ssh/id_rsa", "/proc/1/mem"],
)
def test_posix_protected_paths_are_denied(validator, protected):
    with pytest.raises(PathProtectedError):
        validator.validate(protected)


@pytest.mark.parametrize(
    "unc_or_device",
    [r"\\server\share\file.txt", "//server/share/file.txt", r"\\.\PhysicalDrive0", r"\\?\C:\file"],
)
def test_unc_and_device_paths_are_denied(validator, unc_or_device):
    with pytest.raises(PathNotAllowedError):
        validator.validate(unc_or_device)


@pytest.mark.parametrize(
    "protocol_path", ["smb://server/share/file", "ftp://host/file", "file:///etc/passwd"]
)
def test_protocol_style_paths_are_denied(validator, protocol_path):
    with pytest.raises(PathNotAllowedError):
        validator.validate(protocol_path)


def test_explicitly_denied_path_is_protected_even_inside_an_allowed_root(sandbox):
    denied = sandbox / "secrets"
    policy = PathPolicy(allowed_roots=(sandbox.resolve(),), denied_paths=(denied.resolve(),))
    validator = PathValidator(policy)
    with pytest.raises(PathProtectedError):
        validator.validate(str(denied / "api_key.txt"))


def test_policy_rejects_empty_allowed_roots():
    with pytest.raises(ValueError):
        PathPolicy(allowed_roots=())
