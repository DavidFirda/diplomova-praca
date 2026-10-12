"""questions.instruction_sk - strojový preklad zadania úlohy do slovenčiny

Idempotentná migrácia (stĺpec sa pridá, len ak ešte neexistuje). Hodnoty dopĺňa
`flask bootstrap` zo stĺpca Instruction_SK v final_dataset.csv.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns("questions")}
    if "instruction_sk" not in cols:
        op.add_column("questions", sa.Column("instruction_sk", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("questions", "instruction_sk")
