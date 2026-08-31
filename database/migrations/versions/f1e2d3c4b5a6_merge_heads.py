"""Merge two independent migration heads into one.

Head 2a025fb1f8a8 (phase-7 tool/integration/plugin platform) and
head a1b2c3d4e5f6 (extended application-registry seed) both branched
from 51aedcfad492 and were developed on parallel branches. This merge
migration makes them a single head so 'alembic upgrade head' works
without requiring a branch label.

Revision ID: f1e2d3c4b5a6
Revises: 2a025fb1f8a8, a1b2c3d4e5f6
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, tuple, None] = ('2a025fb1f8a8', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
