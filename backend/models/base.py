from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 轻量列迁移：（无 alembic）启动时为已存在的老库补列
_COLUMN_MIGRATIONS = {
    "workspaces": {
        "sync_exclusions": "ALTER TABLE workspaces ADD COLUMN sync_exclusions TEXT NOT NULL DEFAULT '[]'",
    },
}


def ensure_columns() -> None:
    """检查并补齐老库缺失的列（create_all 不会修改已存在的表）"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, ddl in columns.items():
                if col not in existing:
                    conn.execute(text(ddl))
