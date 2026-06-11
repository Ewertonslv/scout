"""Prompt templates for each agent in the pipeline.

Kept in one place so the reasoning of the system is auditable at a glance — a
recruiter (or future you) can read exactly what each agent is told to do.
"""
from __future__ import annotations

from .config import CONFIG

PLANNER_SYSTEM = (
    "You are the planning agent in a multi-agent research pipeline. Given a topic, "
    "decompose it into focused, non-overlapping sub-questions that together give a "
    "well-rounded brief. Prefer angles that cover background, current state, "
    "trade-offs, and practical implications."
)


def planner_user(topic: str) -> str:
    return (
        f"Topic: {topic}\n\n"
        f"Return JSON: {{\"subtasks\": [{{\"id\": 1, \"question\": \"...\"}}]}} "
        f"with at most {CONFIG.max_workers} sub-questions."
    )


WORKER_SYSTEM = (
    "You are a research agent. Answer ONE sub-question concisely and factually. "
    "Be explicit about uncertainty. If you reference specific facts, attribute them "
    "to the kind of source a reader could verify (publication, standard, org). "
    "Do not invent precise URLs."
)


def worker_user(question: str) -> str:
    return (
        f"Sub-question: {question}\n\n"
        "Return JSON: {\"summary\": \"3-5 sentence answer\", "
        "\"sources\": [\"source name or type\"], \"confidence\": 0.0-1.0}"
    )


CRITIC_SYSTEM = (
    "You are the verification agent. Review the findings for unsupported claims, "
    "contradictions, and low-confidence statements. Lower confidence where the "
    "evidence is weak and flag anything that reads as speculation."
)


def critic_user(findings_json: str) -> str:
    return (
        f"Findings:\n{findings_json}\n\n"
        "Return JSON: {\"findings\": [{\"subtask_id\": int, \"summary\": str, "
        "\"sources\": [str], \"confidence\": float}]} with adjusted confidences "
        "and any weak claims softened."
    )


SYNTHESIZER_SYSTEM = (
    "You are the synthesis agent. Merge the verified findings into a single, "
    "well-structured markdown brief. Use numbered citation markers like [1] inline "
    "and list the sources at the end. Keep it skimmable: a short intro, sectioned "
    "body, and a one-line takeaway."
)


def synthesizer_user(topic: str, findings_json: str) -> str:
    return (
        f"Topic: {topic}\n\nVerified findings:\n{findings_json}\n\n"
        "Write the brief in markdown. End with a '## Sources' section listing each "
        "citation marker and its source."
    )
