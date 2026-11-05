"""Add listings.image_url: the store's photo of the product

Revision ID: 0003
Revises: 0002
Created: 2026-11-05

Listings saved before this get their photo at their next check.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("listings") as batch:
        batch.add_column(sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("listings") as batch:
        batch.drop_column("image_url")
