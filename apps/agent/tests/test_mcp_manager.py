import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import asyncio
from transport.manager import MCPManager


@pytest.fixture
async def manager():
    m = MCPManager()
    yield m
    await m.close_all()


@pytest.mark.asyncio
async def test_stdio_bank_connects_and_lists_tools(manager):
    await manager.add_server({
        "name": "bank",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_bank"],
    })

    tools = manager.get_tools()
    assert len(tools) == 6
    assert {t.name for t in tools} == {
        "list_accounts", "get_balance", "get_transactions",
        "transfer_funds", "freeze_account", "unfreeze_account",
    }


@pytest.mark.asyncio
async def test_stdio_bank_calls_tool(manager):
    await manager.add_server({
        "name": "bank",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_bank"],
    })

    result = await manager.call_tool("bank__list_accounts", {})
    assert len(result) == 1
    assert result[0]["type"] == "text"
    accounts = json.loads(result[0]["text"])[0]["accounts"]
    assert len(accounts) == 4


@pytest.mark.asyncio
async def test_close_all_cleans_up_without_error(manager):
    await manager.add_server({
        "name": "bank",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_bank"],
    })

    await manager.call_tool("bank__list_accounts", {})
    await manager.close_all()

    assert manager.get_tools() == []
