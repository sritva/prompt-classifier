"""add explanation_details and reflection_prompt

Revision ID: 5f10c2a8e06e
Revises: 23b55b974f5b
Create Date: 2026-08-19 22:36:40.795108

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f10c2a8e06e'
down_revision: Union[str, Sequence[str], None] = '23b55b974f5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('prompt_records', sa.Column('explanation_details', sa.String(), nullable=True))
    op.add_column('prompt_records', sa.Column('reflection_prompt', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('prompt_records', 'reflection_prompt')
    op.drop_column('prompt_records', 'explanation_details')
