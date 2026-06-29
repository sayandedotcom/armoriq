import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from transport.manager import MCPManager
from policy.engine import PolicyEngine
from store.models import RuleStore, ApprovalStore, LogStore
from store.db import db
from agent.llm import LLMClient
from agent.loop import Agent
from models import Rule, RuleType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


rule_store = RuleStore()
approval_store = ApprovalStore()
log_store = LogStore()
mcp_manager = MCPManager()
policy_engine = PolicyEngine(rule_store)
llm: LLMClient | None = None
agent: Agent | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class RuleCreate(BaseModel):
    name: str
    rule_type: RuleType
    enabled: bool = True
    priority: int = 0
    config: dict[str, Any] = {}


class RuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    config: dict[str, Any] | None = None


class ApprovalAction(BaseModel):
    approval_id: str
    action: str


connected_websockets: list[WebSocket] = []


async def broadcast(message: dict):
    for ws in connected_websockets[:]:
        try:
            await ws.send_json(message)
        except Exception:
            connected_websockets.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm, agent

    logger.info("Starting Armoriq Agent...")

    load_dotenv()
    logger.info("Environment variables loaded from .env")

    try:
        llm = LLMClient()
        logger.info("LLM client initialized")
    except ValueError as e:
        logger.warning(f"LLM not initialized: {e}")

    agent = Agent(
        llm=llm,
        mcp_manager=mcp_manager,
        policy_engine=policy_engine,
        approval_store=approval_store,
        log_store=log_store,
    )
    app.state.agent = agent

    try:
        with open("servers.json") as f:
            servers = json.load(f).get("servers", [])
        for server_config in servers:
            try:
                config = dict(server_config)
                if config.get("name") == "tavily" and config.get("transport") == "streamable_http":
                    tavily_key = os.environ.get("TAVILY_API_KEY", "")
                    if tavily_key:
                        url = config["url"]
                        sep = "&" if "?" in url else "?"
                        config["url"] = f"{url}{sep}tavilyApiKey={tavily_key}"
                    else:
                        logger.warning("TAVILY_API_KEY not set, skipping Tavily server")
                        continue
                await mcp_manager.add_server(config)
                logger.info(f"Connected to MCP server: {config['name']}")
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {server_config['name']}: {e}")
    except FileNotFoundError:
        logger.warning("servers.json not found, no MCP servers configured")

    logger.info("Armoriq Agent started successfully")

    yield

    logger.info("Shutting down Armoriq Agent...")
    await mcp_manager.close_all()
    db.close()
    logger.info("Armoriq Agent stopped")


app = FastAPI(title="Armoriq Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mcp_servers": list(mcp_manager._connections.keys()),
        "llm_ready": llm is not None,
    }


@app.post("/chat")
async def chat(request: ChatRequest, background: BackgroundTasks):
    if not agent or not llm:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def run_chat():
        try:
            result = await agent.chat(request.conversation_id, request.message)
            await broadcast({
                "type": "chat_response",
                "conversation_id": request.conversation_id,
                "content": result["content"],
                "token_usage": result["token_usage"],
            })
        except Exception as e:
            logger.error(f"Chat error: {e}")
            await broadcast({
                "type": "error",
                "message": str(e),
            })

    background.add_task(run_chat)

    return {"status": "processing", "conversation_id": request.conversation_id}


@app.get("/tools")
async def list_tools():
    tools = mcp_manager.get_tools()
    return {
        "tools": [
            {
                "name": f"{t.server_name}__{t.name}",
                "description": t.description,
                "input_schema": t.input_schema,
                "server_name": t.server_name,
            }
            for t in tools
        ]
    }


@app.get("/rules")
async def list_rules():
    rules = rule_store.get_all()
    return {"rules": [r.model_dump() for r in rules]}


@app.post("/rules")
async def create_rule(rule: RuleCreate):
    new_rule = Rule(
        name=rule.name,
        rule_type=rule.rule_type,
        enabled=rule.enabled,
        priority=rule.priority,
        config=rule.config,
    )
    created = rule_store.create(new_rule)
    await broadcast({"type": "rule_created", "rule": created.model_dump()})
    return {"rule": created.model_dump()}


@app.put("/rules/{rule_id}")
async def update_rule(rule_id: str, updates: RuleUpdate):
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    updated = rule_store.update(rule_id, update_dict)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    await broadcast({"type": "rule_updated", "rule": updated.model_dump()})
    return {"rule": updated.model_dump()}


@app.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    if not rule_store.delete(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    await broadcast({"type": "rule_deleted", "rule_id": rule_id})
    return {"status": "deleted", "rule_id": rule_id}


@app.get("/approvals")
async def list_approvals():
    approvals = approval_store.get_pending()
    return {
        "approvals": [
            {
                "id": a.id,
                "tool_call": a.tool_call.model_dump(),
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
            for a in approvals
        ]
    }


@app.post("/approvals")
async def handle_approval(action: ApprovalAction, request: Request):
    current_agent: Agent | None = getattr(request.app.state, "agent", None)

    approval = approval_store.get_by_id(action.approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if action.action == "approve":
        approval_store.approve(action.approval_id)
        if current_agent:
            tool_call = approval.tool_call
            namespaced_name = f"{tool_call.server_name}__{tool_call.name}"
            try:
                mcp_result = await mcp_manager.call_tool(namespaced_name, tool_call.arguments)
                current_agent.resolve_approval(action.approval_id, True, {
                    "status": "approved",
                    "executed": True,
                    "result": mcp_result,
                })
            except Exception as e:
                current_agent.resolve_approval(action.approval_id, True, {
                    "status": "approved",
                    "executed": False,
                    "error": str(e),
                })
    elif action.action == "reject":
        approval_store.reject(action.approval_id)
        if current_agent:
            current_agent.resolve_approval(action.approval_id, False, {"status": "rejected"})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await broadcast({
        "type": "approval_updated",
        "approval_id": action.approval_id,
        "action": action.action,
    })

    return {"status": "success", "approval_id": action.approval_id, "action": action.action}


@app.get("/logs")
async def list_logs(conversation_id: str | None = None, limit: int = 100):
    if conversation_id:
        logs = log_store.get_by_conversation(conversation_id)
    else:
        logs = log_store.get_recent(limit)
    return {
        "logs": [
            {
                **l.model_dump(),
                "decision": l.decision.value if l.decision else None,
            }
            for l in logs
        ]
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_websockets.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        if ws in connected_websockets:
            connected_websockets.remove(ws)


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
