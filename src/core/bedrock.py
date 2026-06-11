"""Thin wrapper over the Bedrock Converse API.

The Converse API gives a single uniform shape across Amazon Nova and Anthropic
Claude, so switching models is one config flag (see ``Config.model_for``). Every
call returns the text plus token usage so callers can charge the ``TokenBudget``.

The boto3 client is injected to keep this unit-testable without AWS — tests pass
a stub; Lambda passes the real ``bedrock-runtime`` client.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .budget import TokenBudget
from .config import CONFIG


@dataclass
class ModelReply:
    text: str
    input_tokens: int
    output_tokens: int


class BedrockClient:
    def __init__(self, runtime: Any = None) -> None:
        # Lazy import so the module loads in environments without boto3 (e.g. the
        # frontend tooling) and so tests can inject a stub before any AWS import.
        if runtime is None:
            import boto3

            runtime = boto3.client("bedrock-runtime", region_name=CONFIG.region)
        self._runtime = runtime

    def converse(
        self,
        *,
        system: str,
        user: str,
        quality: bool = False,
        max_tokens: int | None = None,
        budget: TokenBudget | None = None,
    ) -> ModelReply:
        if budget is not None:
            budget.check()

        model_id = CONFIG.model_for(quality)
        max_tokens = max_tokens or CONFIG.max_tokens_per_call

        resp = self._runtime.converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
        )

        text = resp["output"]["message"]["content"][0]["text"]
        usage = resp.get("usage", {})
        reply = ModelReply(
            text=text,
            input_tokens=int(usage.get("inputTokens", 0)),
            output_tokens=int(usage.get("outputTokens", 0)),
        )
        if budget is not None:
            budget.charge(reply.input_tokens, reply.output_tokens)
        return reply

    def converse_json(
        self,
        *,
        system: str,
        user: str,
        quality: bool = False,
        max_tokens: int | None = None,
        budget: TokenBudget | None = None,
    ) -> tuple[Any, ModelReply]:
        """Converse and parse the reply as JSON, tolerating ```json fences."""
        reply = self.converse(
            system=system + "\nRespond with ONLY valid JSON, no prose.",
            user=user,
            quality=quality,
            max_tokens=max_tokens,
            budget=budget,
        )
        return _parse_json(reply.text), reply


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # strip a leading ```json / ``` fence and the trailing ```
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned.strip())
