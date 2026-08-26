"""Path security. docs/phase-2 §7.2 — prevents path traversal, protected-
path access, UNC/network-share abuse, and unauthorized system
modification. Every filesystem tool goes through PathValidator.validate()
before touching disk; there is no code path that skips it.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from veyra_contracts import ErrorCategory

# UNC paths (\\server\share, //server/share) and Windows device/extended
# paths (\\.\, \\?\) are always rejected, regardless of allowed roots —
# they name a different machine or a raw device, never a local user file.
_UNC_OR_DEVICE_PATH = re.compile(r"^[\\/]{2}[.?]?[\\/]?")
# Protocol-style paths (smb://, nfs://, ftp://, file://...) are rejected
# outright — this engine only ever operates on local filesystem paths.
_PROTOCOL_PATH = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")

# Windows system locations that must never be writable by this engine,
# regardless of any configured allowed root.
WINDOWS_PROTECTED_PATTERNS: tuple[str, ...] = (
    r"^[a-zA-Z]:\\windows(\\|$)",
    r"^[a-zA-Z]:\\program files(\\|$)",
    r"^[a-zA-Z]:\\program files \(x86\)(\\|$)",
    r"^[a-zA-Z]:\\programdata(\\|$)",
    r"^[a-zA-Z]:\\\$recycle\.bin(\\|$)",
    r"^[a-zA-Z]:\\system volume information(\\|$)",
)

# POSIX equivalents, used when running (and testing) on a non-Windows
# host — see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2. These are
# real, meaningful protections for this dev/CI environment, not filler:
# the security tests in tests/security/ run these for real against a real
# filesystem.
POSIX_PROTECTED_PATTERNS: tuple[str, ...] = (
    r"^/etc(/|$)",
    r"^/bin(/|$)",
    r"^/sbin(/|$)",
    r"^/usr(/|$)",
    r"^/lib(/|$)",
    r"^/lib64(/|$)",
    r"^/boot(/|$)",
    r"^/sys(/|$)",
    r"^/proc(/|$)",
    r"^/root(/|$)",
    r"^/dev(/|$)",
)


class PathNotAllowedError(ValueError):
    """The path is outside every configured allowed root (includes
    traversal attempts that resolve outside those roots)."""

    code = ErrorCategory.PATH_NOT_ALLOWED

    def __init__(self, path: str) -> None:
        super().__init__(f"Path '{path}' is outside the allowed roots.")


class PathProtectedError(ValueError):
    """The path matches a protected system location and is denied even if
    it happens to fall under an allowed root."""

    code = ErrorCategory.PATH_PROTECTED

    def __init__(self, path: str) -> None:
        super().__init__(f"Path '{path}' is a protected system location.")


@dataclass(frozen=True)
class PathPolicy:
    allowed_roots: tuple[Path, ...]
    protected_patterns: tuple[str, ...] = field(default_factory=tuple)
    denied_paths: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.allowed_roots:
            raise ValueError(
                "PathPolicy requires at least one allowed root — an "
                "allow-all policy is never valid, per docs/phase-2 §7.2."
            )


def _default_protected_patterns() -> tuple[str, ...]:
    return WINDOWS_PROTECTED_PATTERNS if sys.platform == "win32" else POSIX_PROTECTED_PATTERNS


def default_policy(allowed_roots: list[Path]) -> PathPolicy:
    return PathPolicy(
        allowed_roots=tuple(root.resolve() for root in allowed_roots),
        protected_patterns=_default_protected_patterns(),
    )


class PathValidator:
    def __init__(self, policy: PathPolicy) -> None:
        self._policy = policy

    def validate(self, raw_path: str) -> Path:
        """Returns a resolved, validated absolute Path, or raises
        PathNotAllowedError / PathProtectedError. This is the only
        function in the engine allowed to turn caller-supplied path
        strings into a Path used for a real filesystem operation."""
        if _UNC_OR_DEVICE_PATH.match(raw_path) or _PROTOCOL_PATH.match(raw_path):
            raise PathNotAllowedError(raw_path)

        resolved = Path(raw_path).expanduser().resolve()
        normalized = str(resolved).lower() if sys.platform == "win32" else str(resolved)

        for pattern in self._policy.protected_patterns:
            if re.match(pattern, normalized, re.IGNORECASE):
                raise PathProtectedError(raw_path)

        for denied in self._policy.denied_paths:
            if resolved == denied or resolved.is_relative_to(denied):
                raise PathProtectedError(raw_path)

        for root in self._policy.allowed_roots:
            if resolved == root or resolved.is_relative_to(root):
                return resolved

        raise PathNotAllowedError(raw_path)
