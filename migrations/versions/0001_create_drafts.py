"""Create the initial draft table and adopt databases created by earlier releases."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0001_create_drafts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the draft table or record the legacy table as the initial schema."""
    inspector = inspect(op.get_bind())
    if "drafts" in inspector.get_table_names():
        columns = {column["name"]: column for column in inspector.get_columns("drafts")}
        expected = {"stream_id", "base", "working"}
        compatible = (
            set(columns) == expected
            and str(columns["stream_id"]["type"]).upper() == "INTEGER"
            and columns["stream_id"]["primary_key"] == 1
            and str(columns["base"]["type"]).upper() == "TEXT"
            and not columns["base"]["nullable"]
            and str(columns["working"]["type"]).upper() == "TEXT"
            and not columns["working"]["nullable"]
        )
        if not compatible:
            raise RuntimeError("Existing drafts table does not match the expected schema")
        return

    op.create_table(
        "drafts",
        sa.Column("stream_id", sa.Integer(), primary_key=True),
        sa.Column("base", sa.Text(), nullable=False),
        sa.Column("working", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    """Remove draft data when explicitly downgrading before the initial revision."""
    op.drop_table("drafts")
