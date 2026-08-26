"""seed conservative default settings

Seeds VEYRA's secure-by-default posture as literal database rows, per
docs/security/05-DATA-PROTECTION.md §3: microphone, screen observation,
external devices, and remote access are OFF unless the user explicitly
enables them. AI/Voice/Vision/Computer Control all start NOT CONFIGURED /
NOT ENABLED, matching the Phase 1 status UI (product brief §40).

Revision ID: bdcb05c63501
Revises: 51aedcfad492
Create Date: 2026-08-26 12:40:05.087688

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db.seed_defaults import DEFAULT_SETTINGS as _DEFAULT_SETTINGS


# revision identifiers, used by Alembic.
revision: str = 'bdcb05c63501'
down_revision: Union[str, None] = '51aedcfad492'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

settings_table = sa.table(
    "system_settings",
    sa.column("id", sa.String),
    sa.column("key", sa.String),
    sa.column("value", sa.JSON),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
)


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        settings_table,
        [
            {
                "id": str(uuid.uuid4()),
                "key": key,
                "value": value,
                "created_at": now,
                "updated_at": now,
            }
            for key, value in _DEFAULT_SETTINGS.items()
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        settings_table.delete().where(settings_table.c.key.in_(_DEFAULT_SETTINGS.keys()))
    )
