"""Seed extended application registry — Chrome, Firefox, Edge, VS Code,
Spotify, VLC, Word, Excel, PowerPoint, Teams, Slack, Paint, Snipping Tool,
Settings, CMD, PowerShell, and more. All entries follow the same
discover-don't-assume pattern as the Phase 2 seed: candidate executable
names only, paths resolved at runtime via PATH search.

Revision ID: a1b2c3d4e5f6
Revises: bdcb05c63501
Create Date: 2026-08-31 00:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'bdcb05c63501'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Extended application registry — the user said VEYRA should act like
# a mini Jarvis and open any common app. Each entry uses executable
# candidates that Windows PATH resolution can find; absolute paths are
# never assumed (docs/phase-2 §20).
_ENTRIES = [
    # Browsers
    {
        "identifier": "chrome",
        "name": "Google Chrome",
        "aliases": ["google chrome", "chrome.exe"],
        "executable_candidates": ["chrome.exe", "google-chrome"],
        "publisher": "Google",
        "risk_level": "SAFE",
    },
    {
        "identifier": "firefox",
        "name": "Mozilla Firefox",
        "aliases": ["firefox.exe", "mozilla"],
        "executable_candidates": ["firefox.exe", "firefox"],
        "publisher": "Mozilla",
        "risk_level": "SAFE",
    },
    {
        "identifier": "edge",
        "name": "Microsoft Edge",
        "aliases": ["msedge", "msedge.exe", "microsoft edge"],
        "executable_candidates": ["msedge.exe", "microsoft-edge"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "brave",
        "name": "Brave Browser",
        "aliases": ["brave.exe", "brave browser"],
        "executable_candidates": ["brave.exe", "brave"],
        "publisher": "Brave Software",
        "risk_level": "SAFE",
    },
    # Development
    {
        "identifier": "vscode",
        "name": "Visual Studio Code",
        "aliases": ["vs code", "visual studio code", "code", "code.exe"],
        "executable_candidates": ["code.cmd", "code.exe", "code"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "cmd",
        "name": "Command Prompt",
        "aliases": ["command prompt", "cmd.exe", "terminal"],
        "executable_candidates": ["cmd.exe"],
        "publisher": "Microsoft",
        "risk_level": "MODERATE",
    },
    {
        "identifier": "powershell",
        "name": "PowerShell",
        "aliases": ["powershell.exe", "ps"],
        "executable_candidates": ["pwsh.exe", "powershell.exe"],
        "publisher": "Microsoft",
        "risk_level": "MODERATE",
    },
    # Media
    {
        "identifier": "spotify",
        "name": "Spotify",
        "aliases": ["spotify.exe"],
        "executable_candidates": ["spotify.exe", "Spotify.exe"],
        "publisher": "Spotify AB",
        "risk_level": "SAFE",
    },
    {
        "identifier": "vlc",
        "name": "VLC Media Player",
        "aliases": ["vlc.exe", "media player", "vlc player"],
        "executable_candidates": ["vlc.exe", "vlc"],
        "publisher": "VideoLAN",
        "risk_level": "SAFE",
    },
    {
        "identifier": "windows_media_player",
        "name": "Windows Media Player",
        "aliases": ["wmplayer", "wmplayer.exe", "media player"],
        "executable_candidates": ["wmplayer.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    # Microsoft Office
    {
        "identifier": "word",
        "name": "Microsoft Word",
        "aliases": ["word.exe", "ms word", "microsoft word", "winword"],
        "executable_candidates": ["winword.exe", "WINWORD.EXE"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "excel",
        "name": "Microsoft Excel",
        "aliases": ["excel.exe", "ms excel", "microsoft excel"],
        "executable_candidates": ["excel.exe", "EXCEL.EXE"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "powerpoint",
        "name": "Microsoft PowerPoint",
        "aliases": ["powerpnt", "powerpnt.exe", "ms powerpoint", "microsoft powerpoint"],
        "executable_candidates": ["powerpnt.exe", "POWERPNT.EXE"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "outlook",
        "name": "Microsoft Outlook",
        "aliases": ["outlook.exe", "ms outlook", "microsoft outlook"],
        "executable_candidates": ["outlook.exe", "OUTLOOK.EXE"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    # Communication
    {
        "identifier": "teams",
        "name": "Microsoft Teams",
        "aliases": ["teams.exe", "ms teams", "microsoft teams"],
        "executable_candidates": ["ms-teams.exe", "Teams.exe", "msteams"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "slack",
        "name": "Slack",
        "aliases": ["slack.exe"],
        "executable_candidates": ["slack.exe", "Slack.exe"],
        "publisher": "Salesforce",
        "risk_level": "SAFE",
    },
    {
        "identifier": "discord",
        "name": "Discord",
        "aliases": ["discord.exe"],
        "executable_candidates": ["discord.exe", "Discord.exe"],
        "publisher": "Discord Inc.",
        "risk_level": "SAFE",
    },
    {
        "identifier": "zoom",
        "name": "Zoom",
        "aliases": ["zoom.exe", "zoom meetings"],
        "executable_candidates": ["Zoom.exe", "zoom.exe"],
        "publisher": "Zoom Video Communications",
        "risk_level": "SAFE",
    },
    # Utilities
    {
        "identifier": "paint",
        "name": "Paint",
        "aliases": ["mspaint", "mspaint.exe", "ms paint"],
        "executable_candidates": ["mspaint.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "snipping_tool",
        "name": "Snipping Tool",
        "aliases": ["snip", "snippingtool", "snippet"],
        "executable_candidates": ["SnippingTool.exe", "snippingtool.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "settings",
        "name": "Windows Settings",
        "aliases": ["windows settings", "ms-settings", "settings app"],
        "executable_candidates": ["ms-settings:"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "task_manager",
        "name": "Task Manager",
        "aliases": ["taskmgr", "taskmgr.exe"],
        "executable_candidates": ["taskmgr.exe"],
        "publisher": "Microsoft",
        "risk_level": "MODERATE",
    },
    {
        "identifier": "wordpad",
        "name": "WordPad",
        "aliases": ["wordpad.exe", "write"],
        "executable_candidates": ["wordpad.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "sticky_notes",
        "name": "Sticky Notes",
        "aliases": ["stikynot", "sticky note", "stickynotes"],
        "executable_candidates": ["stikynot.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
]

applications_table = sa.table(
    "applications",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("identifier", sa.String),
    sa.column("aliases", sa.JSON),
    sa.column("executable_candidates", sa.JSON),
    sa.column("publisher", sa.String),
    sa.column("risk_level", sa.String),
    sa.column("enabled", sa.Boolean),
    sa.column("verification_strategy", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
)


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    # Skip entries whose identifier already exists to make the migration
    # idempotent (safe to run even if some entries were added manually).
    conn = op.get_bind()
    existing_result = conn.execute(
        sa.text("SELECT identifier FROM applications")
    )
    existing = {row[0] for row in existing_result}

    new_entries = [e for e in _ENTRIES if e["identifier"] not in existing]
    if not new_entries:
        return

    op.bulk_insert(
        applications_table,
        [
            {
                "id": str(uuid.uuid4()),
                "name": entry["name"],
                "identifier": entry["identifier"],
                "aliases": entry["aliases"],
                "executable_candidates": entry["executable_candidates"],
                "publisher": entry["publisher"],
                "risk_level": entry["risk_level"],
                "enabled": True,
                "verification_strategy": "process_and_window_detection",
                "created_at": now,
                "updated_at": now,
            }
            for entry in new_entries
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM applications WHERE identifier IN ({})".format(
                ",".join(f"'{e['identifier']}'" for e in _ENTRIES)
            )
        )
    )
