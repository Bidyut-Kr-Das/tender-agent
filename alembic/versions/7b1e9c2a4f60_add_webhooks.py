"""add webhooks

Revision ID: 7b1e9c2a4f60
Revises: 4d4c7cb6a74f
Create Date: 2026-09-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7b1e9c2a4f60'
down_revision: Union[str, Sequence[str], None] = '4d4c7cb6a74f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('webhooks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('client_id', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
    sa.Column('secret', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('events', postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhooks_client_id'), 'webhooks', ['client_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_webhooks_client_id'), table_name='webhooks')
    op.drop_table('webhooks')
