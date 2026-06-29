from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import uuid

from models import Rule, RuleType, LogEntry, ApprovalRequest, ToolCall, Decision

Base = declarative_base()


class DBRule(Base):
    __tablename__ = "rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    rule_type = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DBLogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=True)
    tool_arguments = Column(JSON, nullable=True)
    decision = Column(String, nullable=True)
    rule_id = Column(String, nullable=True)
    rule_name = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    token_used = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)


class DBApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_call_id = Column(String, nullable=False, unique=True)
    tool_name = Column(String, nullable=False)
    server_name = Column(String, nullable=False)
    tool_arguments = Column(JSON, nullable=False)
    conversation_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    timeout_seconds = Column(Integer, default=300)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class Database:
    def __init__(self, url: str = "sqlite:///./armoriq.db"):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool if url.startswith("sqlite") else None,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def session(self) -> Session:
        return self.SessionLocal()

    def close(self):
        self.engine.dispose()


db = Database()
