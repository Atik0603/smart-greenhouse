from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Every model class inherits from this. SQLAlchemy tracks every
    subclass of Base and registers its table definition onto
    Base.metadata automatically, which is what Alembic diffs against.
    """
    pass