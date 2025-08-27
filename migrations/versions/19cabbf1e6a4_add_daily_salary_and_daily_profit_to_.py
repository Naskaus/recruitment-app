"""MANUAL - Add daily salary and profit to PerformanceRecord

Revision ID: <le NOUVEL identifiant de révision ici>
Revises: create_contract_calculations
Create Date: 2025-08-26 23:59:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
# REMPLACEZ CECI par le nouvel ID de révision (le nom du fichier)
revision = '<le NOUVEL identifiant de révision ici>' 
down_revision = 'create_contract_calculations' # Vérifiez que c'est bien la révision précédente
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('performance_record', sa.Column('daily_salary', sa.Float(), nullable=True))
    op.add_column('performance_record', sa.Column('daily_profit', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('performance_record', 'daily_profit')
    op.drop_column('performance_record', 'daily_salary')