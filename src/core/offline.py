"""Offline mode: run the full pipeline with no AWS and no external LLM.

Enabled by ``SCOUT_OFFLINE=1`` (see ``Config.offline``). It swaps two things:

* ``OfflineBedrockClient`` — a deterministic, in-process stand-in for Bedrock. It
  is NOT a language model: it routes on the agent's system prompt and emits
  structured, topic-derived text so the four agents chain into a coherent, cited
  brief. Great for a laptop demo, a CI smoke test, or a recruiter clicking around
  at zero cost. It never invents specific facts — the prose is intentionally
  meta/methodological so nothing reads as a verified claim.
* ``InMemoryJobRepository`` — a dict-backed job store + daily counter, so the API
  runs without DynamoDB.

Both subclass their real counterparts so the type surface (and mypy) is unchanged;
they only override the boto3-touching parts.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .bedrock import BedrockClient, ModelReply
from .budget import TokenBudget
from .config import CONFIG
from .models import Job
from .repo import DailyCapReached, JobRepository

_TOPIC_RE = re.compile(r"Topic:\s*(.+)")
_QUESTION_RE = re.compile(r"Sub-question:\s*(.+)")


def _topic_in(user: str) -> str:
    m = _TOPIC_RE.search(user)
    return m.group(1).strip() if m else "the topic"

# A small, fixed pool of source *types* (never fabricated URLs) cited round-robin.
_SOURCES = [
    "peer-reviewed literature review",
    "industry practitioner survey",
    "official standard / reference documentation",
    "vendor engineering blog (primary source)",
]


def _subtasks_for(topic: str) -> list[dict[str, Any]]:
    angles = [
        f"What problem does {topic} address, and why does it matter now?",
        f"What is the current state of the art and the common approaches to {topic}?",
        f"What are the main trade-offs, risks, and open challenges of {topic}?",
    ]
    return [{"id": i, "question": q} for i, q in enumerate(angles[: CONFIG.max_workers], 1)]


def _summary_for(question: str) -> str:
    q = question.lower()
    if "problem" in q or "matter" in q:
        return (
            "This area exists to solve a concrete, recurring pain point, and interest "
            "has grown as the surrounding tooling matured and costs fell. The core "
            "motivation is usually a mix of efficiency, reliability, and reach that "
            "older approaches struggled to deliver together. Adoption is uneven: it "
            "pays off clearly for some use cases and is overkill for others."
        )
    if "state of the art" in q or "approach" in q or "current" in q:
        return (
            "Practitioners have converged on a handful of dominant patterns rather than "
            "a single winner, and the choice between them is driven by scale, team "
            "maturity, and constraints. Managed and open options both exist, trading "
            "control against operational burden. The frontier is moving quickly, so "
            "specifics date fast — the patterns are more durable than any one tool."
        )
    if "trade-off" in q or "risk" in q or "challenge" in q:
        return (
            "The main tension is between capability and complexity: the more powerful "
            "setups add moving parts, cost, and cognitive load. Common risks are "
            "lock-in, unpredictable spend at scale, and debugging difficulty across "
            "distributed components. Teams that succeed tend to start small, measure, "
            "and only add sophistication when a real constraint forces it."
        )
    return (
        "A well-rounded answer weighs the benefits against the cost and complexity for "
        "the specific context, since the right call is rarely universal. Evidence here "
        "is directional rather than precise, and should be validated against your own "
        "constraints before acting."
    )


class OfflineBedrockClient(BedrockClient):
    """Deterministic, in-process stand-in for the Bedrock Converse API."""

    def __init__(self) -> None:  # noqa: D401 — deliberately skips boto3 setup
        self._runtime = None

    # --- token accounting kept realistic so budgets/guardrails still exercise ---
    @staticmethod
    def _charge(budget: TokenBudget | None, in_tok: int, out_tok: int) -> ModelReply:
        if budget is not None:
            budget.check()
            budget.charge(in_tok, out_tok)
        return ModelReply(text="", input_tokens=in_tok, output_tokens=out_tok)

    def converse_json(
        self,
        *,
        system: str,
        user: str,
        quality: bool = False,
        max_tokens: int | None = None,
        budget: TokenBudget | None = None,
    ) -> tuple[Any, ModelReply]:
        reply = self._charge(budget, 140, 90)
        if "planning agent" in system:
            return {"subtasks": _subtasks_for(_topic_in(user))}, reply
        if "research agent" in system:
            m = _QUESTION_RE.search(user)
            question = m.group(1).strip() if m else "the sub-question"
            # Deterministic but varied per angle, so different findings cite
            # different source *types* (never fabricated URLs).
            source = _SOURCES[len(question) % len(_SOURCES)]
            return (
                {
                    "summary": _summary_for(question),
                    "sources": [source],
                    "confidence": 0.75,
                },
                reply,
            )
        if "verification agent" in system:
            findings = _findings_from(user)
            for i, f in enumerate(findings):
                # Critic softens: cap confidence and attach a second source type.
                f["confidence"] = min(float(f.get("confidence", 0.6)), 0.7)
                f.setdefault("sources", []).append(_SOURCES[(i + 1) % len(_SOURCES)])
            return {"findings": findings}, reply
        return {}, reply

    def converse(
        self,
        *,
        system: str,
        user: str,
        quality: bool = False,
        max_tokens: int | None = None,
        budget: TokenBudget | None = None,
    ) -> ModelReply:
        reply = self._charge(budget, 220, 260)
        reply.text = _render_brief(_topic_in(user), _findings_from(user))
        return reply


def _findings_from(user: str) -> list[dict[str, Any]]:
    """Pull the first complete JSON array embedded in a critic/synthesizer prompt.

    The prompts also contain ``[...]`` in their trailing instructions, so we can't
    just take the last ``]`` — scan from the first ``[`` to its matching close,
    skipping brackets inside string literals.
    """
    start = user.find("[")
    if start == -1:
        return []
    depth, in_str, esc = 0, False, False
    for i in range(start, len(user)):
        ch = user[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(user[start : i + 1])
                    return data if isinstance(data, list) else []
                except json.JSONDecodeError:
                    return []
    return []


def _render_brief(topic: str, findings: list[dict[str, Any]]) -> str:
    lines = [
        f"# {topic}: research brief",
        "",
        "*Produced by scout's multi-agent pipeline: planner → parallel workers → "
        "critic → synthesizer. Offline demo mode uses a deterministic stub in place "
        "of Bedrock, so this brief illustrates the shape of the output, not verified "
        "facts.*",
        "",
        "## Overview",
        f"The sections below break {topic} into focused angles, each researched by a "
        "dedicated worker agent and then checked by a critic before synthesis.",
        "",
        "## Findings",
    ]
    sources: list[str] = []
    for i, f in enumerate(findings, 1):
        question = f.get("question", f"Angle {i}")
        summary = f.get("summary", "")
        lines += [f"### {i}. {question}", f"{summary} [{i}]", ""]
        src = (f.get("sources") or ["general reference"])[0]
        sources.append(f"[{i}] {src}")
    lines += [
        "## Takeaway",
        f"{topic} rewards a start-small, measure-first approach — adopt sophistication "
        "only when a real constraint demands it.",
        "",
        "## Sources",
        *sources,
        "",
    ]
    return "\n".join(lines)


class InMemoryJobRepository(JobRepository):
    """Dict-backed job store + daily counter — no DynamoDB."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._counter: dict[str, int] = {}

    def create(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    def reserve_daily_slot(self, day: str, limit: int | None = None) -> int:
        limit = limit if limit is not None else CONFIG.max_runs_per_day
        count = self._counter.get(day, 0)
        if count >= limit:
            raise DailyCapReached(f"daily cap of {limit} runs reached")
        count += 1
        self._counter[day] = count
        return count
