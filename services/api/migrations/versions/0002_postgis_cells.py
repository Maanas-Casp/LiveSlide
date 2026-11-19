from alembic import op
from sqlalchemy import text

revision = "0002_postgis_cells"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    bind.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    bind.execute(text("ALTER TABLE cells ADD COLUMN IF NOT EXISTS geom geometry(Polygon, 4326)"))
    bind.execute(text("""UPDATE cells SET geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
                        WHERE geom IS NULL"""))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_cells_geom ON cells USING GIST (geom)"))
    bind.execute(text("""CREATE OR REPLACE FUNCTION liveslide_set_cell_geom() RETURNS trigger AS $$
                        BEGIN
                          NEW.geom := ST_MakeEnvelope(NEW.min_lon, NEW.min_lat, NEW.max_lon, NEW.max_lat, 4326);
                          RETURN NEW;
                        END; $$ LANGUAGE plpgsql"""))
    bind.execute(text("DROP TRIGGER IF EXISTS cells_geom_sync ON cells"))
    bind.execute(text("""CREATE TRIGGER cells_geom_sync BEFORE INSERT OR UPDATE OF min_lon, min_lat, max_lon, max_lat
                        ON cells FOR EACH ROW EXECUTE FUNCTION liveslide_set_cell_geom()"""))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(text("DROP TRIGGER IF EXISTS cells_geom_sync ON cells"))
        bind.execute(text("DROP FUNCTION IF EXISTS liveslide_set_cell_geom()"))
        bind.execute(text("DROP INDEX IF EXISTS ix_cells_geom"))
        bind.execute(text("ALTER TABLE cells DROP COLUMN IF EXISTS geom"))
