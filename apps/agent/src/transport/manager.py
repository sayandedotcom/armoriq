import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


class StdioClient:
    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process
        self._request_id = 0
        self._pending: dict[str, asyncio.Future[dict]] = {}
        self._read_task: asyncio.Task | None = None

    async def _read_loop(self):
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode())
                    if "id" in msg:
                        req_id = str(msg["id"])
                        if req_id in self._pending:
                            future = self._pending.pop(req_id)
                            future.set_result(msg)
                except json.JSONDecodeError:
                    pass
        except asyncio.CancelledError:
            pass

    async def _send(self, method: str, params: dict | None = None) -> dict:
        req_id = str(self._request_id)
        self._request_id += 1

        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params:
            msg["params"] = params

        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        line = json.dumps(msg) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        return await asyncio.wait_for(future, timeout=30)

    async def initialize(self) -> dict:
        result = await self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {"listChanged": True}},
            "clientInfo": {"name": "armoriq-agent", "version": "0.1.0"},
        })
        await self._notification("notifications/initialized")
        return result

    async def _notification(self, method: str, params: dict | None = None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        line = json.dumps(msg) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def list_tools(self) -> list[MCPTool]:
        result = await self._send("tools/list")
        tools = result.get("result", {}).get("tools", [])
        return tools

    async def call_tool(self, name: str, arguments: dict) -> list[dict]:
        result = await self._send("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        content = result.get("result", {}).get("content", [])
        return content

    async def _cleanup(self):
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._process.kill()

    def start_reading(self):
        self._read_task = asyncio.create_task(self._read_loop())


class _ProcessManager:
    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process

    async def __aenter__(self):
        return self._process

    async def __aexit__(self, *args):
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._process.kill()


class MCPConnection:
    def __init__(self, name: str, client: StdioClient | None = None, session: ClientSession | None = None):
        self.name = name
        self._client = client
        self._session = session
        self._tools: list[MCPTool] = []
        self.healthy = True

    async def list_tools(self) -> list[MCPTool]:
        if self._session:
            resp = await self._session.list_tools()
            self._tools = [
                MCPTool(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema if hasattr(t, 'inputSchema') else {},
                    server_name=self.name,
                )
                for t in resp.tools
            ]
        elif self._client:
            raw_tools = await self._client.list_tools()
            self._tools = [
                MCPTool(
                    name=t["name"] if isinstance(t, dict) else t.name,
                    description=t.get("description", "") if isinstance(t, dict) else (t.description or ""),
                    input_schema=t.get("inputSchema", {}) if isinstance(t, dict) else {},
                    server_name=self.name,
                )
                for t in raw_tools
            ]
        return self._tools

    async def call_tool(self, name: str, arguments: dict) -> list[dict]:
        if self._session:
            result = await self._session.call_tool(name, arguments)
            content = []
            for item in (result.content if hasattr(result, 'content') else result):
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        content.append({"type": "text", "text": item.get("text", "")})
                    else:
                        content.append(item)
                else:
                    content.append({"type": "text", "text": str(item)})
            return content
        elif self._client:
            result = await self._client.call_tool(name, arguments)
            content = []
            for item in result:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        content.append({"type": "text", "text": item.get("text", "")})
                    else:
                        content.append(item)
                else:
                    content.append({"type": "text", "text": str(item)})
            return content
        raise RuntimeError(f"Connection '{self.name}' has no client or session")


class MCPManager:
    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}
        self._tools: list[MCPTool] = []
        self._lock = asyncio.Lock()
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def add_server(self, config: dict):
        name = config["name"]
        if name in self._connections:
            await self.remove_server(name)

        transport = config.get("transport", "stdio")

        if transport == "stdio":
            command = config["command"]
            args = list(config.get("args", []))
            env = config.get("env")

            full_env = {**os.environ}
            if env:
                full_env.update(env)

            proc = await asyncio.create_subprocess_exec(
                sys.executable if command == "python" else command,
                *args,
                env=full_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await self._exit_stack.enter_async_context(_ProcessManager(proc))

            client = StdioClient(proc)
            client.start_reading()
            await client.initialize()

            conn = MCPConnection(name, client=client)
            self._connections[name] = conn

            tools = await conn.list_tools()
            async with self._lock:
                self._tools = [
                    t for t in self._tools if t.server_name != name
                ] + tools

            logger.info(f"Added MCP server '{name}' with {len(tools)} tools")

        elif transport == "streamable_http":
            url = config["url"]
            headers = config.get("headers") or {}

            # The SDK transport has no `headers` kwarg; custom headers (e.g.
            # bearer auth) must be supplied via a pre-built httpx client. URL-token
            # auth (as Tavily uses) needs none of this and is injected upstream in
            # main.py, so the common case stays header-free.
            if headers:
                import httpx

                http_client = httpx.AsyncClient(headers=headers, follow_redirects=True)
                self._exit_stack.push_async_callback(http_client.aclose)
                http_context = streamable_http_client(url, http_client=http_client)
            else:
                http_context = streamable_http_client(url)

            read, write, _ = await self._exit_stack.enter_async_context(http_context)
            session = ClientSession(read, write)
            await self._exit_stack.enter_async_context(session)
            await session.initialize()

            conn = MCPConnection(name, session=session)
            self._connections[name] = conn

            resp = await session.list_tools()
            tools = [
                MCPTool(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema if hasattr(t, 'inputSchema') else {},
                    server_name=name,
                )
                for t in resp.tools
            ]

            async with self._lock:
                self._tools = [
                    t for t in self._tools if t.server_name != name
                ] + tools

            logger.info(f"Added MCP server '{name}' with {len(tools)} tools")

        else:
            raise ValueError(f"Unsupported transport: {transport}")

    async def remove_server(self, name: str):
        if name in self._connections:
            self._connections[name].healthy = False
            del self._connections[name]
            async with self._lock:
                self._tools = [t for t in self._tools if t.server_name != name]
            logger.info(f"Removed MCP server '{name}'")

    async def call_tool(self, namespaced_name: str, arguments: dict) -> list[dict]:
        if "__" not in namespaced_name:
            raise ValueError(f"Invalid namespaced tool name: {namespaced_name}")

        server_name, tool_name = namespaced_name.split("__", 1)
        conn = self._connections.get(server_name)
        if not conn:
            raise ValueError(f"Unknown server: {server_name}")

        if not conn.healthy:
            raise RuntimeError(f"Connection '{server_name}' is not healthy")

        return await conn.call_tool(tool_name, arguments)

    def get_tools(self) -> list[MCPTool]:
        return list(self._tools)

    def get_tool_by_name(self, name: str) -> MCPTool | None:
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    async def close_all(self):
        await self._exit_stack.aclose()
        self._connections.clear()
        self._tools.clear()
