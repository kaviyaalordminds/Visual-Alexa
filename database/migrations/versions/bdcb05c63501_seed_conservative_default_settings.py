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


# revision identifiers, used by Alembic.
revision: str = 'bdcb05c63501'
down_revision: Union[str, None] = '51aedcfad492'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Real bug found and fixed in Phase 7 (docs/phase-7/PHASE-7-TEST-RESULTS.md):
# this migration used to import the *live* app.db.seed_defaults.
# DEFAULT_SETTINGS dict instead of embedding its own frozen snapshot of
# what Phase 1 actually seeded. Every migration is a point-in-time
# record of what it does — importing a dict that keeps growing (Phase 5
# added 16 more keys to that same dict) meant this migration silently
# started re-seeding Phase 5's voice.*/wake_word.*/stt.*/tts.*/audio.*
# keys too, which then collided with c1a2f3b4d5e6 (the migration Phase 5
# actually wrote to seed exactly those keys, whose own docstring already
# assumed "the pre-existing keys were already seeded by bdcb05c63501" —
# true only for the keys frozen here, never true of a live import).
# `alembic upgrade head` from an empty database has therefore always
# raised a UNIQUE constraint violation on system_settings.key; nothing
# caught it because the test suite (and every dev run) creates its
# schema via Base.metadata.create_all, never by replaying migrations
# from scratch. Frozen here to exactly the 10 keys Phase 1 actually
# shipped, matching this migration's own historical intent.
_PHASE_1_DEFAULT_SETTINGS: dict[str, object] = {
    "microphone.enabled": False,
    "screen_observation.enabled": False,
    "external_devices.enabled": False,
    "remote_access.enabled": False,
    "ai.mode": None,
    "ai.configured": False,
    "voice.configured": False,
    "vision.configured": False,
    "computer_control.enabled": False,
    "security.active": True,
}

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
            for key, value in _PHASE_1_DEFAULT_SETTINGS.items()
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        settings_table.delete().where(settings_table.c.key.in_(_PHASE_1_DEFAULT_SETTINGS.keys()))
    )
