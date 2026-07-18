from sqlalchemy import DateTime
from sqlmodel import SQLModel

from app import models  # noqa: F401 - registers tables on SQLModel.metadata


def test_all_four_tables_are_registered():
    assert set(SQLModel.metadata.tables.keys()) == {
        "users",
        "conversations",
        "messages",
        "documents",
    }


def test_conversations_index_matches_ddl():
    index_names = {ix.name for ix in SQLModel.metadata.tables["conversations"].indexes}
    assert "idx_conversations_user" in index_names


def test_messages_index_and_role_check_match_ddl():
    table = SQLModel.metadata.tables["messages"]
    index_names = {ix.name for ix in table.indexes}
    constraint_names = {c.name for c in table.constraints}
    assert "idx_messages_conversation" in index_names
    assert "ck_messages_role" in constraint_names


def test_documents_indexes_and_status_check_match_ddl():
    table = SQLModel.metadata.tables["documents"]
    index_names = {ix.name for ix in table.indexes}
    constraint_names = {c.name for c in table.constraints}
    assert {"idx_documents_user", "idx_documents_status"} <= index_names
    assert "ck_documents_status" in constraint_names


def test_all_timestamp_columns_are_timezone_aware():
    """Section 4 DDL declares every timestamp column as TIMESTAMPTZ."""
    timestamp_columns = [
        (table_name, col.name)
        for table_name, table in SQLModel.metadata.tables.items()
        for col in table.columns
        if isinstance(col.type, DateTime)
    ]
    assert timestamp_columns, "expected at least one timestamp column"
    for table_name, col_name in timestamp_columns:
        table = SQLModel.metadata.tables[table_name]
        col = table.columns[col_name]
        assert col.type.timezone is True, f"{table_name}.{col_name} must be TIMESTAMPTZ"
