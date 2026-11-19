from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # The initial SQLite/PostgreSQL-neutral schema is declared in SQLAlchemy models.
    from liveslide_api.db import Base
    from liveslide_api import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade():
    from liveslide_api.db import Base
    from liveslide_api import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
