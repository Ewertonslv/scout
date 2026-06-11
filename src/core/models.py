"""Pydantic models shared across the API and the agent Lambdas.

These double as the contract between Step Functions states: each agent receives
and returns a slice of this shape, serialized to/from JSON by the state machine.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RESEARCHING = "RESEARCHING"
    VERIFYING = "VERIFYING"
    SYNTHESIZING = "SYNTHESIZING"
    DONE = "DONE"
    FAILED = "FAILED"


class SubmitRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    quality: bool = False  # opt-in Claude Haiku 4.5 "quality mode"


class Subtask(BaseModel):
    id: int
    question: str


class Finding(BaseModel):
    subtask_id: int
    question: str
    summary: str
    # Source attribution. In v1 these are model-attributed references; Phase 6
    # swaps in retrieval-verified sources (see README).
    sources: list[str] = Field(default_factory=list)
    confidence: float = 0.5


class Citation(BaseModel):
    marker: str  # e.g. "[1]"
    source: str


class Brief(BaseModel):
    topic: str
    markdown: str
    citations: list[Citation] = Field(default_factory=list)


class Job(BaseModel):
    job_id: str
    topic: str
    quality: bool = False
    status: JobStatus = JobStatus.PENDING
    created_at: int  # epoch seconds
    ttl: int  # epoch seconds (DynamoDB TTL attribute)
    brief: Brief | None = None
    error: str | None = None
    tokens_used: int = 0
