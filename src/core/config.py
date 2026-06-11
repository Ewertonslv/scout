"""Central configuration, read once from the environment.

Every tunable lives here so the Lambdas, the API and the tests share a single
source of truth. Defaults are chosen to keep the stack inside the AWS free tier
(see README cost section).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # --- AWS / infra ---
    region: str = os.environ.get("AWS_REGION", "us-east-1")
    jobs_table: str = os.environ.get("JOBS_TABLE", "scout-jobs")
    state_machine_arn: str = os.environ.get("STATE_MACHINE_ARN", "")

    # --- Bedrock models (Converse API ids) ---
    # Default = Amazon Nova Lite (ultra cheap). "Quality mode" = Claude Haiku 4.5.
    model_fast: str = os.environ.get("MODEL_FAST", "amazon.nova-lite-v1:0")
    model_quality: str = os.environ.get("MODEL_QUALITY", "anthropic.claude-haiku-4-5")

    # --- Cost guardrails ---
    max_workers: int = int(os.environ.get("MAX_WORKERS", "3"))
    max_tokens_per_call: int = int(os.environ.get("MAX_TOKENS_PER_CALL", "1500"))
    # Hard ceiling on cumulative tokens for a single research run.
    max_tokens_per_run: int = int(os.environ.get("MAX_TOKENS_PER_RUN", "40000"))
    # Reject new jobs past this many runs in a UTC day (Bedrock spend cap).
    max_runs_per_day: int = int(os.environ.get("MAX_RUNS_PER_DAY", "100"))

    # --- Housekeeping ---
    job_ttl_days: int = int(os.environ.get("JOB_TTL_DAYS", "7"))

    def model_for(self, quality: bool) -> str:
        return self.model_quality if quality else self.model_fast


CONFIG = Config()
