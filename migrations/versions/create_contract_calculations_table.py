"""Create ContractCalculations table

Revision ID: create_contract_calculations
Revises: 39b9dd67d036
Create Date: 2025-08-26 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_contract_calculations'
down_revision = '39b9dd67d036'
branch_labels = None
depends_on = None


def upgrade():
    # Create contract_calculations table
    op.create_table('contract_calculations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('total_salary', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_commission', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_profit', sa.Float(), nullable=True, default=0.0),
        sa.Column('days_worked', sa.Integer(), nullable=True, default=0),
        sa.Column('total_drinks', sa.Integer(), nullable=True, default=0),
        sa.Column('total_special_comm', sa.Float(), nullable=True, default=0.0),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignment.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assignment_id', name='uq_contract_calc_assignment')
    )


def downgrade():
    # Remove table
    op.drop_table('contract_calculations')
