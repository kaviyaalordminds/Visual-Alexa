"""phase 7: tool/integration/plugin platform schema

Revision ID: 2a025fb1f8a8
Revises: c1a2f3b4d5e6
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a025fb1f8a8'
down_revision: Union[str, None] = 'c1a2f3b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tools: mirror ToolDefinition's own Phase 7 additions ---
    op.add_column('tools', sa.Column('keywords', sa.JSON(), nullable=True))
    op.add_column('tools', sa.Column('integration_id', sa.String(length=200), nullable=True))

    # --- integrations: real state machine, scopes, timestamps ---
    op.add_column('integrations', sa.Column('name', sa.String(length=200), nullable=True))
    op.add_column(
        'integrations',
        sa.Column(
            'state',
            sa.Enum(
                'AVAILABLE', 'INSTALL_REQUIRED', 'CONNECT_REQUIRED', 'AUTHORIZING', 'CONNECTED',
                'DISCONNECTED', 'EXPIRED', 'REVOKED', 'ERROR', 'UNAVAILABLE',
                name='integrationstate',
            ),
            nullable=True,
        ),
    )
    op.add_column('integrations', sa.Column('scopes', sa.JSON(), nullable=True))
    op.add_column('integrations', sa.Column('connected_at', sa.DateTime(), nullable=True))
    op.add_column('integrations', sa.Column('last_health_check_at', sa.DateTime(), nullable=True))

    # --- devices: the strictly-ordered pairing-stage marker ---
    op.add_column(
        'devices',
        sa.Column(
            'pairing_stage',
            sa.Enum(
                'PAIR', 'IDENTIFY', 'AUTHENTICATE', 'AUTHORIZE', 'REGISTER_CAPABILITIES',
                'CONTROL',
                name='devicepairingstage',
            ),
            nullable=True,
        ),
    )

    # --- plugins / plugin_permissions: new tables ---
    op.create_table(
        'plugins',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('manifest_id', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('author', sa.String(length=200), nullable=False),
        sa.Column(
            'state',
            sa.Enum(
                'UNTRUSTED', 'REVIEW_REQUIRED', 'TRUSTED', 'ENABLED', 'DISABLED', 'REVOKED',
                name='pluginstate',
            ),
            nullable=False,
        ),
        sa.Column('manifest', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('manifest_id'),
    )
    op.create_table(
        'plugin_permissions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('plugin_id', sa.String(), nullable=False),
        sa.Column('permission', sa.String(length=200), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('plugin_permissions')
    op.drop_table('plugins')
    op.drop_column('devices', 'pairing_stage')
    op.drop_column('integrations', 'last_health_check_at')
    op.drop_column('integrations', 'connected_at')
    op.drop_column('integrations', 'scopes')
    op.drop_column('integrations', 'state')
    op.drop_column('integrations', 'name')
    op.drop_column('tools', 'integration_id')
    op.drop_column('tools', 'keywords')
