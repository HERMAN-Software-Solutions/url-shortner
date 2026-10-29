"""add is_active default

Revision ID: 35a7d96f6246
Revises: 1252cc9fea34
Create Date: 2026-10-29 08:32:47.524489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35a7d96f6246'
down_revision: Union[str, Sequence[str], None] = '1252cc9fea34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.alter_column("links", "is_active", server_default=sa.text("true"))


def downgrade() -> None:
    op.alter_column("links", "is_active", server_default=None)