"""phase 2: seed default application registry entries

Seeds registry *entries* only (name/aliases/candidate executable names) —
never a hard-coded absolute path. computer_control.registry always
re-resolves the actual executable path at launch time via PATH search —
see docs/phase-2/APPLICATION-CONTROL.md and docs/phase-2 §20 "do not
assume paths." These three are the exact applications the Phase 2 brief's
own functional test scenarios (§32) reference.

Revision ID: 7a90f572da0d
Revises: 63d3d077887d
Create Date: 2026-08-26 14:21:41.522195

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a90f572da0d'
down_revision: Union[str, None] = '63d3d077887d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENTRIES = [
    {
        "identifier": "notepad",
        "name": "Notepad",
        "aliases": ["notepad.exe"],
        "executable_candidates": ["notepad.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "calculator",
        "name": "Calculator",
        "aliases": ["calc", "calc.exe"],
        "executable_candidates": ["calc.exe"],
        "publisher": "Microsoft",
        "risk_level": "SAFE",
    },
    {
        "identifier": "file_explorer",
        "name": "File Explorer",
        "aliases": ["explorer", "explorer.exe", "files"],
        "executable_candidates": ["explorer.exe"],
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
            for entry in _ENTRIES
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        applications_table.delete().where(
            applications_table.c.identifier.in_([e["identifier"] for e in _ENTRIES])
        )
    )
