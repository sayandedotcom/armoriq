import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_bank.bank import BANK


def test_list_accounts():
    accounts = BANK.list_accounts()
    assert len(accounts) == 4
    assert any(a["id"] == "acc_001" for a in accounts)


def test_get_balance():
    result = BANK.get_balance("acc_001")
    assert result["balance"] == 5000.0
    assert result["frozen"] is False


def test_transfer_funds():
    result = BANK.transfer_funds("acc_001", "acc_002", 500.0)
    assert result["success"] is True
    assert result["from_balance"] == 4500.0
    assert result["to_balance"] == 3500.0


def test_transfer_insufficient_funds():
    try:
        BANK.transfer_funds("acc_001", "acc_002", 10000.0)
        assert False, "Should have raised"
    except ValueError as e:
        assert "Insufficient funds" in str(e)


def test_freeze_account():
    result = BANK.freeze_account("acc_001")
    assert result["frozen"] is True
    assert BANK.accounts["acc_001"].frozen is True


def test_frozen_account_cannot_transfer():
    BANK.freeze_account("acc_003")
    try:
        BANK.transfer_funds("acc_003", "acc_004", 100.0)
        assert False, "Should have raised"
    except ValueError as e:
        assert "frozen" in str(e)


def test_unfreeze_account():
    BANK.unfreeze_account("acc_003")
    assert BANK.accounts["acc_003"].frozen is False
