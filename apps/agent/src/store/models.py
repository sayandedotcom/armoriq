from store.db import db, DBRule, DBLogEntry, DBApprovalRequest
from models import Rule, RuleType, LogEntry, ApprovalRequest, ToolCall, Decision
from datetime import datetime, timedelta
import uuid
import asyncio


class RuleStore:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def get_all(self) -> list[Rule]:
        with db.session() as s:
            db_rules = s.query(DBRule).all()
            return [self._db_to_rule(r) for r in db_rules]

    def get_enabled(self) -> list[Rule]:
        with db.session() as s:
            db_rules = s.query(DBRule).filter(DBRule.enabled == True).all()
            return [self._db_to_rule(r) for r in db_rules]

    def get_by_id(self, rule_id: str) -> Rule | None:
        with db.session() as s:
            db_rule = s.query(DBRule).filter(DBRule.id == rule_id).first()
            return self._db_to_rule(db_rule) if db_rule else None

    def create(self, rule: Rule) -> Rule:
        with db.session() as s:
            db_rule = DBRule(
                id=rule.id or str(uuid.uuid4()),
                name=rule.name,
                rule_type=rule.rule_type.value,
                enabled=rule.enabled,
                priority=rule.priority,
                config=rule.config,
            )
            s.add(db_rule)
            s.commit()
            s.refresh(db_rule)
            result = self._db_to_rule(db_rule)
        return result

    def update(self, rule_id: str, updates: dict) -> Rule | None:
        with db.session() as s:
            db_rule = s.query(DBRule).filter(DBRule.id == rule_id).first()
            if not db_rule:
                return None
            for key, value in updates.items():
                if key == "rule_type":
                    setattr(db_rule, key, value.value if hasattr(value, "value") else value)
                elif key == "config":
                    setattr(db_rule, key, value)
                elif hasattr(db_rule, key):
                    setattr(db_rule, key, value)
            db_rule.updated_at = datetime.utcnow()
            s.commit()
            s.refresh(db_rule)
            result = self._db_to_rule(db_rule)
        return result

    def delete(self, rule_id: str) -> bool:
        with db.session() as s:
            db_rule = s.query(DBRule).filter(DBRule.id == rule_id).first()
            if not db_rule:
                return False
            s.delete(db_rule)
            s.commit()
        return True

    def subscribe(self, q: asyncio.Queue):
        self._subscribers.append(q)

    async def _broadcast(self, message: dict):
        for q in self._subscribers:
            await q.put(message)

    @staticmethod
    def _db_to_rule(db_rule: DBRule) -> Rule:
        return Rule(
            id=db_rule.id,
            name=db_rule.name,
            rule_type=RuleType(db_rule.rule_type),
            enabled=db_rule.enabled,
            priority=db_rule.priority,
            config=db_rule.config or {},
            created_at=db_rule.created_at,
            updated_at=db_rule.updated_at,
        )


class ApprovalStore:
    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}

    def create(self, tool_call: ToolCall, timeout_seconds: int = 300) -> ApprovalRequest:
        expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        with db.session() as s:
            db_approval = DBApprovalRequest(
                id=str(uuid.uuid4()),
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                server_name=tool_call.server_name,
                tool_arguments=tool_call.arguments,
                conversation_id=tool_call.conversation_id,
                status="pending",
                timeout_seconds=timeout_seconds,
                expires_at=expires_at,
            )
            s.add(db_approval)
            s.commit()
            s.refresh(db_approval)
            return ApprovalRequest(
                id=db_approval.id,
                tool_call=tool_call,
                status=db_approval.status,
                timeout_seconds=db_approval.timeout_seconds,
                created_at=db_approval.created_at,
                expires_at=db_approval.expires_at,
            )

    def get_pending(self) -> list[ApprovalRequest]:
        with db.session() as s:
            db_approvals = (
                s.query(DBApprovalRequest)
                .filter(DBApprovalRequest.status == "pending")
                .all()
            )
            return [
                ApprovalRequest(
                    id=a.id,
                    tool_call=ToolCall(
                        id=a.tool_call_id,
                        name=a.tool_name,
                        server_name=a.server_name,
                        arguments=a.tool_arguments,
                        conversation_id=a.conversation_id,
                    ),
                    status=a.status,
                    timeout_seconds=a.timeout_seconds,
                    created_at=a.created_at,
                    expires_at=a.expires_at,
                )
                for a in db_approvals
            ]

    def get_by_id(self, approval_id: str) -> ApprovalRequest | None:
        with db.session() as s:
            db_approval = (
                s.query(DBApprovalRequest)
                .filter(DBApprovalRequest.id == approval_id)
                .first()
            )
            if not db_approval:
                return None
            return ApprovalRequest(
                id=db_approval.id,
                tool_call=ToolCall(
                    id=db_approval.tool_call_id,
                    name=db_approval.tool_name,
                    server_name=db_approval.server_name,
                    arguments=db_approval.tool_arguments,
                    conversation_id=db_approval.conversation_id,
                ),
                status=db_approval.status,
                timeout_seconds=db_approval.timeout_seconds,
                created_at=db_approval.created_at,
                expires_at=db_approval.expires_at,
            )

    def approve(self, approval_id: str) -> bool:
        with db.session() as s:
            db_approval = s.query(DBApprovalRequest).filter(DBApprovalRequest.id == approval_id).first()
            if not db_approval:
                return False
            db_approval.status = "approved"
            s.commit()
        return True

    def reject(self, approval_id: str) -> bool:
        with db.session() as s:
            db_approval = s.query(DBApprovalRequest).filter(DBApprovalRequest.id == approval_id).first()
            if not db_approval:
                return False
            db_approval.status = "rejected"
            s.commit()
        return True

    def expire(self, approval_id: str) -> bool:
        with db.session() as s:
            db_approval = s.query(DBApprovalRequest).filter(DBApprovalRequest.id == approval_id).first()
            if not db_approval:
                return False
            db_approval.status = "expired"
            s.commit()
        return True


class LogStore:
    def create(self, entry: LogEntry) -> LogEntry:
        with db.session() as s:
            db_entry = DBLogEntry(
                id=entry.id or str(uuid.uuid4()),
                conversation_id=entry.conversation_id,
                tool_name=entry.tool_name,
                tool_arguments=entry.tool_arguments,
                decision=entry.decision.value if entry.decision else None,
                rule_id=entry.rule_id,
                rule_name=entry.rule_name,
                reason=entry.reason,
                token_used=entry.token_used,
            )
            s.add(db_entry)
            s.commit()
            s.refresh(db_entry)
            return LogEntry(
                id=db_entry.id,
                conversation_id=db_entry.conversation_id,
                tool_name=db_entry.tool_name,
                tool_arguments=db_entry.tool_arguments,
                decision=Decision(db_entry.decision) if db_entry.decision else None,
                rule_id=db_entry.rule_id,
                rule_name=db_entry.rule_name,
                reason=db_entry.reason,
                token_used=db_entry.token_used,
                timestamp=db_entry.timestamp,
            )

    def get_by_conversation(self, conversation_id: str) -> list[LogEntry]:
        with db.session() as s:
            db_entries = (
                s.query(DBLogEntry)
                .filter(DBLogEntry.conversation_id == conversation_id)
                .order_by(DBLogEntry.timestamp)
                .all()
            )
            return [
                LogEntry(
                    id=e.id,
                    conversation_id=e.conversation_id,
                    tool_name=e.tool_name,
                    tool_arguments=e.tool_arguments,
                    decision=Decision(e.decision) if e.decision else None,
                    rule_id=e.rule_id,
                    rule_name=e.rule_name,
                    reason=e.reason,
                    token_used=e.token_used,
                    timestamp=e.timestamp,
                )
                for e in db_entries
            ]

    def get_recent(self, limit: int = 100) -> list[LogEntry]:
        with db.session() as s:
            db_entries = (
                s.query(DBLogEntry)
                .order_by(DBLogEntry.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                LogEntry(
                    id=e.id,
                    conversation_id=e.conversation_id,
                    tool_name=e.tool_name,
                    tool_arguments=e.tool_arguments,
                    decision=Decision(e.decision) if e.decision else None,
                    rule_id=e.rule_id,
                    rule_name=e.rule_name,
                    reason=e.reason,
                    token_used=e.token_used,
                    timestamp=e.timestamp,
                )
                for e in db_entries
            ]
