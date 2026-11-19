from alembic import op
import sqlalchemy as sa

revision = "0003_named_report_locations"
down_revision = "0002_postgis_cells"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("reports")}
    with op.batch_alter_table("reports") as batch:
        if "location_name" not in existing:
            batch.add_column(sa.Column("location_name", sa.String(length=300), nullable=True))
        batch.alter_column("lat", existing_type=sa.Float(), nullable=True)
        batch.alter_column("lon", existing_type=sa.Float(), nullable=True)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("reports")}
    if "location_name" in existing:
        with op.batch_alter_table("reports") as batch:
            batch.drop_column("location_name")
