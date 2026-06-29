from fastmcp import FastMCP

mcp = FastMCP("armoriq-mcp-bank")


from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Account:
    id: str
    name: str
    balance: float
    currency: str = "USD"
    frozen: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Transaction:
    id: str
    account_id: str
    type: str
    amount: float
    target_id: str | None
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "completed"


class MockBank:
    def __init__(self):
        self.accounts: dict[str, Account] = {
            "acc_001": Account(id="acc_001", name="Alice", balance=5000.0),
            "acc_002": Account(id="acc_002", name="Bob", balance=3000.0),
            "acc_003": Account(id="acc_003", name="Charlie", balance=7500.0),
            "acc_004": Account(id="acc_004", name="Diana", balance=1200.0),
        }
        self.transactions: list[Transaction] = []

    def list_accounts(self):
        return [
            {
                "accounts": [
                    {
                        "id": acc.id,
                        "name": acc.name,
                        "balance": acc.balance,
                        "currency": acc.currency,
                        "frozen": acc.frozen,
                    }
                    for acc in self.accounts.values()
                ]
            }
        ]

    def get_balance(self, account_id: str):
        acc = self._get_account(account_id)
        return {
            "account_id": acc.id,
            "name": acc.name,
            "balance": acc.balance,
            "currency": acc.currency,
            "frozen": acc.frozen,
        }

    def get_transactions(self, account_id: str):
        self._get_account(account_id)
        txns = [t for t in self.transactions if t.account_id == account_id]
        return {
            "account_id": account_id,
            "transactions": [
                {
                    "id": t.id,
                    "type": t.type,
                    "amount": t.amount,
                    "target_id": t.target_id,
                    "timestamp": t.timestamp.isoformat(),
                    "status": t.status,
                }
                for t in txns
            ],
        }

    def transfer_funds(self, from_account_id: str, to_account_id: str, amount: float):
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        from_acc = self._get_account(from_account_id)
        to_acc = self._get_account(to_account_id)

        if from_acc.frozen:
            raise ValueError(f"Account {from_account_id} is frozen")
        if to_acc.frozen:
            raise ValueError(f"Account {to_account_id} is frozen")

        if from_acc.balance < amount:
            raise ValueError(f"Insufficient funds: {from_acc.balance} < {amount}")

        from_acc.balance -= amount
        to_acc.balance += amount

        txn_id = f"txn_{len(self.transactions) + 1:04d}"
        self.transactions.append(
            Transaction(
                id=txn_id,
                account_id=from_account_id,
                type="transfer_out",
                amount=amount,
                target_id=to_account_id,
            )
        )
        self.transactions.append(
            Transaction(
                id=f"{txn_id}_r",
                account_id=to_account_id,
                type="transfer_in",
                amount=amount,
                target_id=from_account_id,
            )
        )

        return {
            "success": True,
            "transaction_id": txn_id,
            "from_account": from_account_id,
            "to_account": to_account_id,
            "amount": amount,
            "from_balance": from_acc.balance,
            "to_balance": to_acc.balance,
        }

    def freeze_account(self, account_id: str):
        acc = self._get_account(account_id)
        acc.frozen = True
        return {
            "success": True,
            "account_id": account_id,
            "frozen": True,
            "message": f"Account {account_id} has been frozen",
        }

    def unfreeze_account(self, account_id: str):
        acc = self._get_account(account_id)
        acc.frozen = False
        return {
            "success": True,
            "account_id": account_id,
            "frozen": False,
            "message": f"Account {account_id} has been unfrozen",
        }

    def _get_account(self, account_id: str) -> Account:
        if account_id not in self.accounts:
            raise ValueError(f"Account not found: {account_id}")
        return self.accounts[account_id]


BANK = MockBank()


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
