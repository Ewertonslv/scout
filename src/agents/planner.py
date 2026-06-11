"""Planner agent — decomposes the topic into focused sub-questions.

State in:  {job_id, topic, quality, tokens_used}
State out: + {subtasks: [{id, question}], tokens_used}
"""
from __future__ import annotations

from typing import Any

from core.budget import TokenBudget
from core.config import CONFIG
from core.deps import get_client
from core.prompts import PLANNER_SYSTEM, planner_user


def handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    topic = event["topic"]
    quality = bool(event.get("quality", False))
    budget = TokenBudget(used=int(event.get("tokens_used", 0)))

    data, _reply = get_client().converse_json(
        system=PLANNER_SYSTEM,
        user=planner_user(topic),
        quality=quality,
        budget=budget,
    )

    subtasks = data.get("subtasks", [])[: CONFIG.max_workers]
    # Defensive: ensure ids are present and unique.
    for i, st in enumerate(subtasks, start=1):
        st.setdefault("id", i)

    return {**event, "subtasks": subtasks, "tokens_used": budget.used}
