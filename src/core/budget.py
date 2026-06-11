"""Per-run token budget — the deterministic cost ceiling for a single research run.

Bedrock is the only paid component in the stack, so we bound worst-case spend in
code rather than trusting prompt sizes to stay small. Each agent shares one
``TokenBudget`` (rehydrated from the job's running total between Step Functions
states) and charges it after every model call. Once the ceiling is hit, further
calls raise ``BudgetExceeded`` and the pipeline degrades gracefully instead of
running up a bill.
"""
from __future__ import annotations

from .config import CONFIG


class BudgetExceeded(Exception):
    """Raised when a run would exceed its cumulative token ceiling."""


class TokenBudget:
    def __init__(self, used: int = 0, ceiling: int | None = None) -> None:
        self.used = used
        self.ceiling = ceiling if ceiling is not None else CONFIG.max_tokens_per_run

    @property
    def remaining(self) -> int:
        return max(0, self.ceiling - self.used)

    def check(self) -> None:
        """Call before issuing a model request."""
        if self.remaining <= 0:
            raise BudgetExceeded(
                f"run token ceiling reached ({self.used}/{self.ceiling})"
            )

    def charge(self, input_tokens: int, output_tokens: int) -> None:
        self.used += input_tokens + output_tokens
