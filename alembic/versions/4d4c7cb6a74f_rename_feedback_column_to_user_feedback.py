"""rename feedback column to user_feedback

Revision ID: 4d4c7cb6a74f
Revises: 15c2347f523e
Create Date: 2026-09-29 16:13:18.487691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d4c7cb6a74f'
down_revision: Union[str, Sequence[str], None] = '15c2347f523e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("feedback", "feedback", new_column_name="user_feedback")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("feedback", "user_feedback", new_column_name="feedback")
