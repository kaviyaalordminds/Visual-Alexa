"""phase 5: seed voice default settings

Seeds the new voice.*/wake_word.*/stt.*/tts.*/cloud_fallback.*/audio.*
SystemSetting keys `app/db/seed_defaults.py` added for Phase 5, all
conservative-by-default (voice/wake word/cloud fallback off until the user
explicitly enables them) — docs/security/05-DATA-PROTECTION.md §3, brief
§104-106. Inserts only the new keys, not the full DEFAULT_SETTINGS dict —
the pre-existing keys were already seeded by bdcb05c63501.

Revision ID: c1a2f3b4d5e6
Revises: bffc0ab7b27f
Create Date: 2026-08-26 18:40:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2f3b4d5e6'
down_revision: Union[str, None] = 'bffc0ab7b27f'
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

_NEW_SETTINGS: dict[str, object] = {
    "voice.enabled": False,
    "voice.input_device": None,
    "voice.output_device": None,
    "voice.mode": "WAKE_WORD_ONLY",
    "wake_word.enabled": False,
    "wake_word.phrase": "Hey Veyra",
    "wake_word.sensitivity": 0.5,
    "stt.provider": None,
    "stt.mode": "LOCAL",
    "tts.provider": None,
    "tts.voice": None,
    "tts.speed": 1.0,
    "tts.pitch": 1.0,
    "cloud_fallback.enabled": False,
    "audio.noise_suppression": True,
    "audio.echo_cancellation": True,
}


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
            for key, value in _NEW_SETTINGS.items()
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(settings_table.delete().where(settings_table.c.key.in_(_NEW_SETTINGS.keys())))
