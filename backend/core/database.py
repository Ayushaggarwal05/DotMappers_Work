from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.config import settings
from backend.core.logging import logger

# SQLAlchemy Declarative Base
Base = declarative_base()

# Configure SQLite engine
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# Enable SQLite foreign keys & WAL mode for high concurrency
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize all database tables defined in models."""
    logger.info("Initializing database schema...")
    # Import all models to ensure they are registered with Base
    import backend.models.ticket # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")


def ping_db() -> bool:
    """Check if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database ping failed: {e}")
        return False


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
