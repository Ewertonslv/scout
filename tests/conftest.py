"""Shared fixtures: a moto-backed DynamoDB table and a fake Bedrock client.

Nothing here touches real AWS or Bedrock, so the whole suite runs offline and at
zero cost — the same suite CI runs on every PR.
"""
from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from core.bedrock import ModelReply
from core.budget import TokenBudget
from core.config import CONFIG
from core.repo import JobRepository


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    yield


@pytest.fixture
def jobs_table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName=CONFIG.jobs_table,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def repo(jobs_table) -> JobRepository:
    return JobRepository(table=jobs_table)


class FakeBedrockClient:
    """Deterministic stand-in: routes on the system prompt, charges the budget."""

    def __init__(self) -> None:
        self.calls = 0

    def _reply(self, budget, in_tok=120, out_tok=80) -> ModelReply:
        self.calls += 1
        r = ModelReply(text="", input_tokens=in_tok, output_tokens=out_tok)
        if budget is not None:
            budget.check()
            budget.charge(in_tok, out_tok)
        return r

    def converse_json(self, *, system, user, quality=False, max_tokens=None, budget=None):
        reply = self._reply(budget)
        if "planning agent" in system:
            data = {"subtasks": [{"id": 1, "question": "Q1"}, {"id": 2, "question": "Q2"}]}
        elif "research agent" in system:
            data = {"summary": "A concise answer.", "sources": ["Example Org"], "confidence": 0.8}
        elif "verification agent" in system:
            data = {
                "findings": [
                    {
                        "subtask_id": 1,
                        "question": "Q1",
                        "summary": "A.",
                        "sources": ["Example Org"],
                        "confidence": 0.7,
                    }
                ]
            }
        else:
            data = {}
        return data, reply

    def converse(self, *, system, user, quality=False, max_tokens=None, budget=None):
        reply = self._reply(budget, out_tok=200)
        reply.text = "# Brief\n\nBody with a citation [1].\n\n## Sources\n[1] Example Org\n"
        return reply


@pytest.fixture
def fake_client(monkeypatch):
    from core import deps

    client = FakeBedrockClient()
    deps.set_client(client)
    yield client
    deps._client = None  # reset singleton


@pytest.fixture
def budget() -> TokenBudget:
    return TokenBudget()


@pytest.fixture
def wired(fake_client, repo):
    """Wire both the fake Bedrock client and the moto repo into the deps singletons."""
    from core import deps

    deps.set_repo(repo)
    yield repo
    deps._repo = None
