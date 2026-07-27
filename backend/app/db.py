from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(settings.database_url)

@event.listens_for(engine, "connect")
def _set_search_path(dbapi_connection, connection_record) -> None:
    # Pooled/proxied connections (e.g. Supabase's Supavisor) don't honor the
    # `options=-c search_path=...` DSN param, so set it per real connection instead.
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO knowledgehub, public")
    cursor.close()
    dbapi_connection.commit()
    

def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_engine() -> Engine:
    return engine
