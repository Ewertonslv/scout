"""Critic agent — verifies findings, softens weak claims, adjusts confidence.

State in:  {job_id, topic, quality, tokens_used, research: [{finding, worker_tokens}]}
State out: + {findings: [verified...], tokens_used}
"""
from __future__ import annotations

import json
from typing import Any

from core.budget import TokenBudget
from core.deps import get_client
from core.prompts import CRITIC_SYSTEM, critic_user


def handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    research = event.get("research", [])
    raw_findings = [r["finding"] for r in research]
    worker_tokens = sum(int(r.get("worker_tokens", 0)) for r in research)

    quality = bool(event.get("quality", False))
    budget = TokenBudget(used=int(event.get("tokens_used", 0)) + worker_tokens)

    try:
        data, _reply = get_client().converse_json(
            system=CRITIC_SYSTEM,
            user=critic_user(json.dumps(raw_findings, ensure_ascii=False)),
            quality=quality,
            budget=budget,
        )
        verified = data.get("findings", raw_findings)
    except Exception:  # noqa: BLE001 — degrade to unverified findings on error
        verified = raw_findings

    return {**event, "findings": verified, "tokens_used": budget.used}
