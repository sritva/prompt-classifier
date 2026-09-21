"""add provenance columns

Revision ID: 7a19b8c2d1e0
Revises: 6a19b8c2d1e0
Create Date: 2026-09-21 19:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7a19b8c2d1e0'
down_revision: Union[str, Sequence[str], None] = '6a19b8c2d1e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c['name'] for c in insp.get_columns('prompt_records')]
    if 'model' not in columns:
        op.add_column('prompt_records', sa.Column('model', sa.String(), nullable=True))
    if 'provider' not in columns:
        op.add_column('prompt_records', sa.Column('provider', sa.String(), nullable=True))
    if 'is_heuristic' not in columns:
        op.add_column('prompt_records', sa.Column('is_heuristic', sa.Boolean(), nullable=True, server_default='0'))
    if 'is_cached' not in columns:
        op.add_column('prompt_records', sa.Column('is_cached', sa.Boolean(), nullable=True, server_default='0'))
    if 'original_latency_ms' not in columns:
        op.add_column('prompt_records', sa.Column('original_latency_ms', sa.Integer(), nullable=True))
    if 'original_total_tokens' not in columns:
        op.add_column('prompt_records', sa.Column('original_total_tokens', sa.Integer(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c['name'] for c in insp.get_columns('prompt_records')]
    
    for col in ['model', 'provider', 'is_heuristic', 'is_cached', 'original_latency_ms', 'original_total_tokens']:
        if col in columns:
            op.drop_column('prompt_records', col)
