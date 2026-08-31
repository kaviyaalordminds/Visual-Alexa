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
        import os

        for candidate in entry.executable_candidates:
            # Absolute path — verify it exists directly (no PATH lookup needed).
            if os.path.isabs(candidate):
                if os.path.isfile(candidate):
                    return candidate
                continue
            # Relative name — discover via PATH.
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


# docs/phase-2/APPLICATION-CONTROL.md §"seeded registry".
# Candidates are tried in order: PATH-resolvable short names first so the
# real install location wins on any PATH-configured system; absolute paths
# after as fallbacks for systems where System32 isn't on PATH. Absolute
# paths are only used if `os.path.isfile` confirms they exist on this
# machine (see resolve_executable_path above).
WINDOWS_DEFAULT_ENTRIES: list[ApplicationRegistryEntry] = [
    # ── Microsoft built-ins ──────────────────────────────────────────────
    ApplicationRegistryEntry(
        identifier="notepad",
        name="Notepad",
        aliases=("notepad.exe", "text editor"),
        executable_candidates=(
            "notepad.exe",
            r"C:\Windows\System32\notepad.exe",
            r"C:\Windows\notepad.exe",
            r"C:\Windows\SysWOW64\notepad.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="calculator",
        name="Calculator",
        aliases=("calc", "calc.exe"),
        executable_candidates=(
            "calc.exe",
            r"C:\Windows\System32\calc.exe",
            r"C:\Windows\SysWOW64\calc.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="file_explorer",
        name="File Explorer",
        aliases=("explorer", "explorer.exe", "files", "my computer", "this pc"),
        executable_candidates=(
            "explorer.exe",
            r"C:\Windows\explorer.exe",
            r"C:\Windows\System32\explorer.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="paint",
        name="Paint",
        aliases=("mspaint", "mspaint.exe", "ms paint"),
        executable_candidates=(
            "mspaint.exe",
            r"C:\Windows\System32\mspaint.exe",
            r"C:\Windows\SysWOW64\mspaint.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="wordpad",
        name="WordPad",
        aliases=("wordpad.exe", "write"),
        executable_candidates=(
            "wordpad.exe",
            r"C:\Program Files\Windows NT\Accessories\wordpad.exe",
            r"C:\Program Files (x86)\Windows NT\Accessories\wordpad.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="cmd",
        name="Command Prompt",
        aliases=("cmd.exe", "command prompt", "terminal", "command line"),
        executable_candidates=(
            "cmd.exe",
            r"C:\Windows\System32\cmd.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.MODERATE,
    ),
    ApplicationRegistryEntry(
        identifier="powershell",
        name="PowerShell",
        aliases=("powershell.exe", "ps", "pwsh"),
        executable_candidates=(
            "pwsh.exe",
            "powershell.exe",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Program Files\PowerShell\7\pwsh.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.MODERATE,
    ),
    ApplicationRegistryEntry(
        identifier="task_manager",
        name="Task Manager",
        aliases=("taskmgr", "taskmgr.exe", "task manager"),
        executable_candidates=(
            "taskmgr.exe",
            r"C:\Windows\System32\taskmgr.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="control_panel",
        name="Control Panel",
        aliases=("control", "control.exe"),
        executable_candidates=(
            "control.exe",
            r"C:\Windows\System32\control.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="settings",
        name="Windows Settings",
        aliases=("ms-settings", "windows settings"),
        executable_candidates=(
            "ms-settings:",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="snipping_tool",
        name="Snipping Tool",
        aliases=("snippingtool", "snip", "snipping tool", "screenshot tool"),
        executable_candidates=(
            "SnippingTool.exe",
            r"C:\Windows\System32\SnippingTool.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    # ── Browsers ────────────────────────────────────────────────────────
    ApplicationRegistryEntry(
        identifier="chrome",
        name="Google Chrome",
        aliases=("google chrome", "chrome.exe"),
        executable_candidates=(
            "chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ),
        publisher="Google",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="edge",
        name="Microsoft Edge",
        aliases=("msedge", "msedge.exe", "microsoft edge"),
        executable_candidates=(
            "msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="firefox",
        name="Mozilla Firefox",
        aliases=("firefox.exe",),
        executable_candidates=(
            "firefox.exe",
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ),
        publisher="Mozilla",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="brave",
        name="Brave Browser",
        aliases=("brave.exe", "brave browser"),
        executable_candidates=(
            "brave.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        ),
        publisher="Brave Software",
        risk_level=RiskLevel.SAFE,
    ),
    # ── Microsoft Office ────────────────────────────────────────────────
    ApplicationRegistryEntry(
        identifier="word",
        name="Microsoft Word",
        aliases=("winword", "winword.exe", "ms word"),
        executable_candidates=(
            "winword.exe",
            r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files\Microsoft Office\Office16\WINWORD.EXE",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="excel",
        name="Microsoft Excel",
        aliases=("excel.exe", "ms excel"),
        executable_candidates=(
            "excel.exe",
            r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
            r"C:\Program Files\Microsoft Office\Office16\EXCEL.EXE",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="powerpoint",
        name="Microsoft PowerPoint",
        aliases=("powerpnt", "powerpnt.exe", "ms powerpoint", "ppt"),
        executable_candidates=(
            "powerpnt.exe",
            r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="outlook",
        name="Microsoft Outlook",
        aliases=("outlook.exe", "ms outlook"),
        executable_candidates=(
            "outlook.exe",
            r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    # ── Media & Entertainment ────────────────────────────────────────────
    ApplicationRegistryEntry(
        identifier="vlc",
        name="VLC Media Player",
        aliases=("vlc.exe", "vlc player"),
        executable_candidates=(
            "vlc.exe",
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ),
        publisher="VideoLAN",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="spotify",
        name="Spotify",
        aliases=("spotify.exe",),
        executable_candidates=(
            "spotify.exe",
            r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe",
        ),
        publisher="Spotify",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="windows_media_player",
        name="Windows Media Player",
        aliases=("wmplayer", "wmplayer.exe", "media player"),
        executable_candidates=(
            "wmplayer.exe",
            r"C:\Program Files\Windows Media Player\wmplayer.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    # ── Development tools ───────────────────────────────────────────────
    ApplicationRegistryEntry(
        identifier="vscode",
        name="Visual Studio Code",
        aliases=("code", "code.exe", "vs code", "visual studio code"),
        executable_candidates=(
            "code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="visual_studio",
        name="Visual Studio",
        aliases=("devenv", "devenv.exe", "vs", "visual studio"),
        executable_candidates=(
            "devenv.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\IDE\devenv.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\devenv.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    # ── Communication ───────────────────────────────────────────────────
    ApplicationRegistryEntry(
        identifier="discord",
        name="Discord",
        aliases=("discord.exe",),
        executable_candidates=(
            "discord.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Discord\app-current\Discord.exe",
        ),
        publisher="Discord Inc.",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="teams",
        name="Microsoft Teams",
        aliases=("teams.exe", "ms teams", "microsoft teams"),
        executable_candidates=(
            "ms-teams.exe",
            "teams.exe",
            r"C:\Program Files\WindowsApps\MSTeams_*\ms-teams.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Microsoft\Teams\current\Teams.exe",
        ),
        publisher="Microsoft",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="zoom",
        name="Zoom",
        aliases=("zoom.exe",),
        executable_candidates=(
            "zoom.exe",
            r"C:\Users\%USERNAME%\AppData\Roaming\Zoom\bin\Zoom.exe",
        ),
        publisher="Zoom Video Communications",
        risk_level=RiskLevel.SAFE,
    ),
    ApplicationRegistryEntry(
        identifier="slack",
        name="Slack",
        aliases=("slack.exe",),
        executable_candidates=(
            "slack.exe",
            r"C:\Users\%USERNAME%\AppData\Local\slack\slack.exe",
        ),
        publisher="Salesforce",
        risk_level=RiskLevel.SAFE,
    ),
]
