"""add classifier_version column

Revision ID: 6a19b8c2d1e0
Revises: 5f10c2a8e06e
Create Date: 2026-08-26 10:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6a19b8c2d1e0'
down_revision: Union[str, Sequence[str], None] = '5f10c2a8e06e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c['name'] for c in insp.get_columns('prompt_records')]
    if 'classifier_version' not in columns:
        op.add_column('prompt_records', sa.Column('classifier_version', sa.String(), nullable=True, server_default='2.0.0'))

def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c['name'] for c in insp.get_columns('prompt_records')]
    if 'classifier_version' in columns:
        op.drop_column('prompt_records', 'classifier_version')
