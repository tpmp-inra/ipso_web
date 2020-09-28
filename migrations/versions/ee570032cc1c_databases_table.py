"""databases table

Revision ID: ee570032cc1c
Revises: 5763436b3837
Create Date: 2020-09-16 14:30:29.542430

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ee570032cc1c'
down_revision = '5763436b3837'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('database',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_database_name'), 'database', ['name'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_database_name'), table_name='database')
    op.drop_table('database')
    # ### end Alembic commands ###