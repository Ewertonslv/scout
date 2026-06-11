"""Worker agent — researches ONE sub-question. Runs in parallel via a Map state.

State in:  {job_id, quality, subtask: {id, question}}
State out: {finding: {...}, worker_tokens: int}

Each worker tracks only its own tokens; the critic sums them into the run total.
A worker that fails returns a low-confidence placeholder finding so a single bad
sub-question doesn't sink the whole brief.
"""
from __future__ import annotations

from typing import Any

from core.budget import TokenBudget
from core.deps import get_client
from core.prompts import WORKER_SYSTEM, worker_user


def handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    subtask = event["subtask"]
    quality = bool(event.get("quality", False))
    budget = TokenBudget()

    try:
        data, _reply = get_client().converse_json(
            system=WORKER_SYSTEM,
            user=worker_user(subtask["question"]),
            quality=quality,
            budget=budget,
        )
        finding = {
            "subtask_id": subtask["id"],
            "question": subtask["question"],
            "summary": data.get("summary", ""),
            "sources": data.get("sources", []),
            "confidence": float(data.get("confidence", 0.5)),
        }
    except Exception as exc:  # noqa: BLE001 — never fail the Map item
        finding = {
            "subtask_id": subtask["id"],
            "question": subtask["question"],
            "summary": f"(no answer — agent error: {exc})",
            "sources": [],
            "confidence": 0.0,
        }

    return {"finding": finding, "worker_tokens": budget.used}
