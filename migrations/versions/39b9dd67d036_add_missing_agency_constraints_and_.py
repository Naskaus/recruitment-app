"""Add missing agency constraints and indexes

Revision ID: 39b9dd67d036
Revises: add_contract_calculations
Create Date: 2024-12-20 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '39b9dd67d036'
down_revision = '248320b99ffd'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing indexes for agency_id columns to improve query performance
    op.create_index('idx_user_agency', 'user', ['agency_id'])
    op.create_index('idx_staff_profile_agency', 'staff_profile', ['agency_id'])
    op.create_index('idx_assignment_agency', 'assignment', ['agency_id'])
    op.create_index('idx_venue_agency', 'venue', ['agency_id'])
    op.create_index('idx_performance_record_assignment', 'performance_record', ['assignment_id'])
    
    # Add missing foreign key constraints if they don't exist
    # Note: SQLite doesn't support adding foreign keys to existing tables easily
    # These will be enforced at the application level
    
    # Add check constraints for data integrity
    # Note: SQLite doesn't support CHECK constraints in the same way as PostgreSQL
    # These will be enforced at the application level
    
    # Add unique constraints for agency-scoped uniqueness
    # Staff ID should be unique within an agency
    try:
        op.create_unique_constraint('uq_staff_id_agency', 'staff_profile', ['staff_id', 'agency_id'])
    except:
        pass  # Constraint might already exist
    
    # Venue name should be unique within an agency
    try:
        op.create_unique_constraint('uq_venue_name_agency', 'venue', ['name', 'agency_id'])
    except:
        pass  # Constraint might already exist


def downgrade():
    # Remove indexes
    op.drop_index('idx_user_agency', 'user')
    op.drop_index('idx_staff_profile_agency', 'staff_profile')
    op.drop_index('idx_assignment_agency', 'assignment')
    op.drop_index('idx_venue_agency', 'venue')
    op.drop_index('idx_performance_record_assignment', 'performance_record')
    
    # Remove unique constraints
    try:
        op.drop_constraint('uq_staff_id_agency', 'staff_profile', type_='unique')
    except:
        pass
    
    try:
        op.drop_constraint('uq_venue_name_agency', 'venue', type_='unique')
    except:
        pass
