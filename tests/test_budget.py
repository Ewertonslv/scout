import pytest

from core.budget import BudgetExceeded, TokenBudget


def test_charge_accumulates():
    b = TokenBudget(ceiling=1000)
    b.charge(100, 50)
    assert b.used == 150
    assert b.remaining == 850


def test_check_raises_when_exhausted():
    b = TokenBudget(used=1000, ceiling=1000)
    with pytest.raises(BudgetExceeded):
        b.check()


def test_remaining_never_negative():
    b = TokenBudget(used=1200, ceiling=1000)
    assert b.remaining == 0
