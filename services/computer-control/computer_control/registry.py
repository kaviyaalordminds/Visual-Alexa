"""Application Registry / resolver. docs/phase-2 §6.2, §6.3, §20.

'Open Chrome' must resolve: alias -> known, pre-registered application ->
an executable discovered (never assumed/hard-coded) on this machine ->
launch. An unrecognized name never reaches a launch call at all — there is
no path from arbitrary caller-supplied text to a subprocess argument.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field

from veyra_contracts import ErrorCategory, RiskLevel


class ApplicationNotFoundError(LookupError):
    code = ErrorCategory.APPLICATION_NOT_FOUND

    def __init__(self, query: str) -> None:
        super().__init__(f"No registered, installed application matches '{query}'.")


class ApplicationDisabledError(ValueError):
    code = ErrorCategory.TOOL_DISABLED

    def __init__(self, query: str) -> None:
        super().__init__(f"Application '{query}' is registered but disabled.")


@dataclass(frozen=True)
class ApplicationRegistryEntry:
    identifier: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    # Candidate executable names/paths searched, in order, at resolve time
    # — never a single hard-coded absolute path. docs/phase-2 §20:
    # "the application resolver must discover or validate the
    # installation."
    executable_candidates: tuple[str, ...] = field(default_factory=tuple)
    publisher: str | None = None
    risk_level: RiskLevel = RiskLevel.MODERATE
    enabled: bool = True
    verification_strategy: str = "process_and_window_detection"


class ApplicationRegistry:
    def __init__(self, entries: list[ApplicationRegistryEntry]) -> None:
        self._by_identifier = {e.identifier: e for e in entries}
        self._by_alias: dict[str, ApplicationRegistryEntry] = {}
        for entry in entries:
            for alias in (entry.identifier, entry.name, *entry.aliases):
                self._by_alias[alias.lower()] = entry

    def list_entries(self) -> list[ApplicationRegistryEntry]:
        return list(self._by_identifier.values())

    def resolve_entry(self, query: str) -> ApplicationRegistryEntry:
        entry = self._by_alias.get(query.strip().lower())
        if entry is None:
            raise ApplicationNotFoundError(query)
        if not entry.enabled:
            raise ApplicationDisabledError(query)
        return entry

    def resolve_executable_path(self, entry: ApplicationRegistryEntry) -> str:
        for candidate in entry.executable_candidates:
            found = shutil.which(candidate)
            if found:
                return found
        raise ApplicationNotFoundError(entry.identifier)

    def resolve(self, query: str) -> str:
        """Convenience: alias -> validated, discovered executable path, in
        one call. Raises ApplicationNotFoundError/ApplicationDisabledError
        — never returns a path it couldn't verify exists."""
        entry = self.resolve_entry(query)
        return self.resolve_executable_path(entry)


# docs/phase-2/APPLICATION-CONTROL.md §"seeded registry": three common,
# safe, well-known Windows executables — the exact three the Phase 2
# brief's functional tests (§32) reference. Only registry *entries* are
# seeded; paths are always discovered via resolve_executable_path, never
# assumed.
WINDOWS_DEFAULT_ENTRIES: list[ApplicationRegistryEntry] = [
    ApplicationRegistryEntry(
        identifier="notepad",
        name="Notepad",
        aliases=("notepad.exe",),
        executable_candidates=("notepad.exe",),
        publisher="Microsoft",
        risk_level=RiskLevel.MODERATE,
    ),
    ApplicationRegistryEntry(
        identifier="calculator",
        name="Calculator",
        aliases=("calc", "calc.exe"),
        executable_candidates=("calc.exe",),
        publisher="Microsoft",
        risk_level=RiskLevel.MODERATE,
    ),
    ApplicationRegistryEntry(
        identifier="file_explorer",
        name="File Explorer",
        aliases=("explorer", "explorer.exe", "files"),
        executable_candidates=("explorer.exe",),
        publisher="Microsoft",
        risk_level=RiskLevel.MODERATE,
    ),
]
