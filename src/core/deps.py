"""Lazy singletons for the Bedrock client and the job repository.

Lambdas reuse one instance across warm invocations; tests override these via
``set_client`` / ``set_repo`` so nothing touches AWS.
"""
from __future__ import annotations

from .bedrock import BedrockClient
from .repo import JobRepository

_client: BedrockClient | None = None
_repo: JobRepository | None = None


def get_client() -> BedrockClient:
    global _client
    if _client is None:
        _client = BedrockClient()
    return _client


def get_repo() -> JobRepository:
    global _repo
    if _repo is None:
        _repo = JobRepository()
    return _repo


def set_client(client: BedrockClient) -> None:
    global _client
    _client = client


def set_repo(repo: JobRepository) -> None:
    global _repo
    _repo = repo
