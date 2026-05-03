"""rename image_url to file_path

Revision ID: b7e2f4a1c903
Revises: 3499aace4124
Create Date: 2026-05-03

"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7e2f4a1c903'
down_revision: Union[str, None] = '3499aace4124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('receipts', 'image_url', new_column_name='file_path')


def downgrade() -> None:
    op.alter_column('receipts', 'file_path', new_column_name='image_url')
