"""Synthesizer agent — merges verified findings into a cited markdown brief,
persists the finished job to DynamoDB, and marks it DONE.

State in:  {job_id, topic, quality, tokens_used, findings: [...]}
State out: + {brief, status: DONE}
"""
from __future__ import annotations

import json
import re
from typing import Any

from core.budget import TokenBudget
from core.deps import get_client, get_repo
from core.models import Brief, Citation, JobStatus
from core.prompts import SYNTHESIZER_SYSTEM, synthesizer_user

_CITATION_RE = re.compile(r"^\s*(\[\d+\])\s*[:\-]?\s*(.+)$")


def handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    topic = event["topic"]
    job_id = event["job_id"]
    quality = bool(event.get("quality", False))
    findings = event.get("findings", [])
    budget = TokenBudget(used=int(event.get("tokens_used", 0)))

    reply = get_client().converse(
        system=SYNTHESIZER_SYSTEM,
        user=synthesizer_user(topic, json.dumps(findings, ensure_ascii=False)),
        quality=quality,
        max_tokens=2048,
        budget=budget,
    )
    markdown = reply.text
    citations = [Citation(**c) for c in _extract_citations(markdown)]
    brief = Brief(topic=topic, markdown=markdown, citations=citations)

    repo = get_repo()
    job = repo.get(job_id)
    if job is not None:
        job.status = JobStatus.DONE
        job.tokens_used = budget.used
        job.brief = brief
        repo.save(job)

    return {
        **event,
        "status": JobStatus.DONE.value,
        "tokens_used": budget.used,
        "brief": brief.model_dump(mode="json"),
    }


def _extract_citations(markdown: str) -> list[dict[str, str]]:
    """Pull '[n] source' lines from a trailing Sources section."""
    citations: list[dict[str, str]] = []
    in_sources = False
    for line in markdown.splitlines():
        if line.strip().lower().startswith("## sources"):
            in_sources = True
            continue
        if in_sources:
            m = _CITATION_RE.match(line)
            if m:
                citations.append({"marker": m.group(1), "source": m.group(2).strip()})
    return citations
