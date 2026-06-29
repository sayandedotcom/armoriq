import asyncio
import uuid
import logging
from typing import Any

from agent.llm import LLMClient
from transport.manager import MCPManager
from policy.engine import PolicyEngine
from store.models import ApprovalStore, LogStore
from models import ToolCall, Decision, LogEntry

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        mcp_manager: MCPManager,
        policy_engine: PolicyEngine,
        approval_store: ApprovalStore,
        log_store: LogStore,
    ):
        self.llm = llm
        self.mcp = mcp_manager
        self.policy = policy_engine
        self.approval_store = approval_store
        self.log_store = log_store
        self._conversations: dict[str, list[dict]] = {}
        self._approval_futures: dict[str, asyncio.Future] = {}

    def get_or_create_conversation(self, conversation_id: str) -> list[dict]:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        return self._conversations[conversation_id]

    async def chat(self, conversation_id: str, user_message: str) -> dict[str, Any]:
        conversation = self.get_or_create_conversation(conversation_id)
        conversation.append({"role": "user", "content": user_message})

        self.llm.reset_usage()
        tools = self.mcp.get_tools()
        gemini_tools = self.llm.convert_mcp_tools_to_gemini(tools)

        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            messages = self._build_messages(conversation)
            response = await self.llm.generate_async(messages, tools=gemini_tools)

            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                final_content = response.get("content", "")
                conversation.append({"role": "model", "content": final_content})
                break

            conversation.append({"role": "model", "tool_calls": tool_calls})

            for tc in tool_calls:
                tc_result = await self._execute_tool_call(conversation_id, tc)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", str(uuid.uuid4())),
                    "name": tc["name"],
                    "content": tc_result,
                })
        else:
            conversation.append({
                "role": "system",
                "content": "Max iterations exceeded",
            })

        final_text = ""
        for msg in reversed(conversation):
            if msg.get("role") == "model" and msg.get("content"):
                final_text = msg["content"]
                break

        return {
            "content": final_text,
            "conversation_id": conversation_id,
            "token_usage": self.llm.total_tokens,
        }

    async def _execute_tool_call(self, conversation_id: str, tool_call_data: dict) -> str:
        tool_name = tool_call_data["name"]
        arguments = tool_call_data.get("arguments", {})

        if "__" not in tool_name:
            logger.warning(f"Tool call without namespace: {tool_name}")
            return f"ERROR: Invalid tool name format - {tool_name}"

        server_name, raw_tool_name = tool_name.split("__", 1)

        tool_call = ToolCall(
            id=str(uuid.uuid4()),
            name=tool_name,
            server_name=server_name,
            arguments=arguments,
            conversation_id=conversation_id,
        )

        policy_result = self.policy.evaluate(tool_call, self.llm.total_tokens)

        self.log_store.create(LogEntry(
            conversation_id=conversation_id,
            tool_name=tool_name,
            tool_arguments=arguments,
            decision=policy_result.decision,
            rule_id=policy_result.rule_id,
            reason=policy_result.reason,
        ))

        if policy_result.decision == Decision.DENY:
            logger.info(f"Tool {tool_name} blocked: {policy_result.reason}")
            return f"ERROR: {policy_result.reason}"

        if policy_result.decision == Decision.REQUIRE_APPROVAL:
            logger.info(f"Tool {tool_name} requires approval")
            approval = self.approval_store.create(tool_call)
            result = await self._wait_for_approval(approval.id, tool_call)
            if result.get("error"):
                return str(result)
            if result.get("status") == "rejected":
                return f"ERROR: Approval denied"
            if result.get("status") == "approved" and result.get("executed"):
                return str(result.get("result", {}))
            return str(result)

        try:
            mcp_result = await self.mcp.call_tool(tool_name, arguments)
            result_content = self._format_mcp_result(mcp_result)
            logger.info(f"Tool {tool_name} executed successfully")
            return str(result_content)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return f"ERROR: {str(e)}"

    async def _wait_for_approval(self, approval_id: str, tool_call: ToolCall) -> dict:
        future = asyncio.get_event_loop().create_future()
        self._approval_futures[approval_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=300)
            return result
        except asyncio.TimeoutError:
            self.approval_store.expire(approval_id)
            return {"error": f"Approval request timed out after 300s"}
        finally:
            self._approval_futures.pop(approval_id, None)

    def resolve_approval(self, approval_id: str, approved: bool, result: dict | None = None):
        if approval_id in self._approval_futures:
            future = self._approval_futures[approval_id]
            if approved:
                future.set_result(result or {"status": "approved"})
            else:
                future.set_exception(Exception("Approval denied"))

    def _format_mcp_result(self, mcp_result: Any) -> Any:
        if isinstance(mcp_result, list):
            return [self._format_content_item(item) for item in mcp_result]
        return mcp_result

    def _format_content_item(self, item: dict) -> str:
        if isinstance(item, dict):
            if item.get("type") == "text":
                return item.get("text", "")
            elif item.get("type") == "error":
                return f"Error: {item.get('text', 'Unknown error')}"
            return str(item)
        return str(item)

    def _build_messages(self, conversation: list[dict]) -> list[dict]:
        return list(conversation)
