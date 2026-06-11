"""In-process pipeline runner.

This chains the four agents directly, no Step Functions. It powers two things:

* local dev / `sam local` and tests, where standing up a state machine is overkill
* the Phase-1 MVP synchronous endpoint

In production the identical agent handlers are wired by ``statemachine/pipeline.asl.json``
so the orchestration is real (parallel Map, retries, visible execution graph) — this
runner is the same logic executed sequentially in one process.
"""
from __future__ import annotations

from typing import Any

from agents import critic, planner, synthesizer, worker


def run_pipeline(job_id: str, topic: str, quality: bool = False) -> dict[str, Any]:
    state: dict[str, Any] = {
        "job_id": job_id,
        "topic": topic,
        "quality": quality,
        "tokens_used": 0,
    }

    state = planner.handler(state)

    research = [
        worker.handler({"job_id": job_id, "quality": quality, "subtask": st})
        for st in state.get("subtasks", [])
    ]
    state["research"] = research

    state = critic.handler(state)
    state = synthesizer.handler(state)
    return state
