from fastmcp import FastMCP

from .bank import BANK

mcp = FastMCP("armoriq-mcp-bank")


@mcp.tool()
def list_accounts() -> list:
    """List all bank accounts. Returns account IDs, names, and balances."""
    return BANK.list_accounts()


@mcp.tool()
def get_balance(account_id: str) -> dict:
    """Get the current balance and details for a specific account."""
    return BANK.get_balance(account_id)


@mcp.tool()
def get_transactions(account_id: str) -> dict:
    """Get transaction history for a specific account."""
    return BANK.get_transactions(account_id)


@mcp.tool()
def transfer_funds(from_account_id: str, to_account_id: str, amount: float) -> dict:
    """Transfer funds between two accounts. Requires approval for amounts over $1000."""
    return BANK.transfer_funds(from_account_id, to_account_id, amount)


@mcp.tool()
def freeze_account(account_id: str) -> dict:
    """Freeze a bank account. Frozen accounts cannot send or receive transfers."""
    return BANK.freeze_account(account_id)


@mcp.tool()
def unfreeze_account(account_id: str) -> dict:
    """Unfreeze a previously frozen bank account."""
    return BANK.unfreeze_account(account_id)
