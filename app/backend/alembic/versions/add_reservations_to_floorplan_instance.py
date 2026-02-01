"""add reservations field to floorplan instance

Revision ID: add_reservations_001
Revises: 
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_reservations_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add reservations column to floorplaninstance table
    op.add_column('floorplaninstance', sa.Column('reservations', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    # Set default value for existing rows
    op.execute("UPDATE floorplaninstance SET reservations = '{}'::json WHERE reservations IS NULL")
    # Make it non-nullable
    op.alter_column('floorplaninstance', 'reservations', nullable=False)


def downgrade():
    op.drop_column('floorplaninstance', 'reservations')
