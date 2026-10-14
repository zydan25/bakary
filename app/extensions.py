"""Shared extension instances for the application factory."""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import MetaData

# Predictable constraint names help Alembic create and alter constraints safely.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(
    metadata=MetaData(naming_convention=NAMING_CONVENTION),
    session_options={"expire_on_commit": False},
)
migrate = Migrate(compare_type=True)
login_manager = LoginManager()
csrf = CSRFProtect()
