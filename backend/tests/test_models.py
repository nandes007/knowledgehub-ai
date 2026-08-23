from sqlalchemy import DateTime
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.models import Company, Conversation, Department, Document, Message, User


def test_all_six_tables_are_registered():
    assert set(SQLModel.metadata.tables.keys()) == {
        "companies",
        "departments",
        "users",
        "conversations",
        "messages",
        "documents",
    }


def test_companies_constraints_and_indexes():
    table = SQLModel.metadata.tables["companies"]
    constraint_names = {c.name for c in table.constraints}
    assert "ck_companies_status" in constraint_names
    assert table.columns["name"].unique or any(ix.unique for ix in table.indexes if "name" in ix.columns)


def test_departments_constraints_and_indexes():
    table = SQLModel.metadata.tables["departments"]
    index_names = {ix.name for ix in table.indexes}
    constraint_names = {c.name for c in table.constraints}
    assert "uq_departments_company_name" in constraint_names
    assert "idx_departments_company" in index_names


def test_users_constraints_and_indexes():
    table = SQLModel.metadata.tables["users"]
    index_names = {ix.name for ix in table.indexes}
    constraint_names = {c.name for c in table.constraints}
    assert "ck_users_role" in constraint_names
    assert "ck_users_approval_status" in constraint_names
    assert "idx_users_company" in index_names


def test_conversations_index_matches_ddl():
    table = SQLModel.metadata.tables["conversations"]
    index_names = {ix.name for ix in table.indexes}
    assert "idx_conversations_user" in index_names
    assert "idx_conversations_company" in index_names


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
    assert {"idx_documents_company", "idx_documents_uploaded_by", "idx_documents_status"} <= index_names
    assert "ck_documents_status" in constraint_names
    assert "ck_documents_visibility" in constraint_names


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


def test_round_trip_model_insertion_and_retrieval():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. Create Company
        company = Company(name="Nandes Tech", status="active")
        session.add(company)
        session.commit()
        session.refresh(company)

        # 2. Create Department
        dept = Department(company_id=company.id, name="Engineering")
        session.add(dept)
        session.commit()
        session.refresh(dept)

        # 3. Create User
        user = User(
            company_id=company.id,
            department_id=dept.id,
            email="admin@nandes.tech",
            password_hash="hashed_pw",
            display_name="Nandes Admin",
            role="admin",
            approval_status="approved",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # 4. Create Document
        doc = Document(
            company_id=company.id,
            uploaded_by=user.id,
            filename="handbook.pdf",
            content_type="application/pdf",
            file_path="/uploads/handbook.pdf",
            file_hash="sha256hash",
            status="ready",
            doc_type="policy",
            department_id=dept.id,
            visibility="department",
            chunk_count=5,
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # 5. Create Conversation
        conv = Conversation(
            company_id=company.id,
            user_id=user.id,
            title="Q&A Session",
        )
        session.add(conv)
        session.commit()
        session.refresh(conv)

        # 6. Create Message
        msg = Message(
            conversation_id=conv.id,
            role="user",
            content="Hello KnowledgeHub!",
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)

        # Verify query retrieval
        loaded_company = session.exec(select(Company).where(Company.id == company.id)).first()
        assert loaded_company is not None
        assert loaded_company.name == "Nandes Tech"

        loaded_user = session.exec(select(User).where(User.id == user.id)).first()
        assert loaded_user is not None
        assert loaded_user.company_id == company.id
        assert loaded_user.department_id == dept.id
        assert loaded_user.role == "admin"
        assert loaded_user.approval_status == "approved"

        loaded_doc = session.exec(select(Document).where(Document.id == doc.id)).first()
        assert loaded_doc is not None
        assert loaded_doc.company_id == company.id
        assert loaded_doc.uploaded_by == user.id
        assert loaded_doc.department_id == dept.id

        loaded_conv = session.exec(select(Conversation).where(Conversation.id == conv.id)).first()
        assert loaded_conv is not None
        assert loaded_conv.company_id == company.id
        assert loaded_conv.user_id == user.id

        loaded_msg = session.exec(select(Message).where(Message.id == msg.id)).first()
        assert loaded_msg is not None
        assert loaded_msg.conversation_id == conv.id
