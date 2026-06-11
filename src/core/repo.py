"""DynamoDB persistence for jobs and the daily run counter.

Single table, on-demand billing, TTL-cleaned. Two item shapes share it:

* job items   — PK ``JOB#<job_id>``
* a counter   — PK ``COUNTER#<utc-date>`` used to enforce the daily run cap

The boto3 resource is injected so tests can pass a ``moto`` table.
"""
from __future__ import annotations

import time
from typing import Any

from botocore.exceptions import ClientError

from .config import CONFIG
from .models import Job, JobStatus


class DailyCapReached(Exception):
    """Raised when the UTC-day run cap is hit (cost guardrail)."""


class JobRepository:
    def __init__(self, table: Any = None) -> None:
        if table is None:
            import boto3

            table = boto3.resource("dynamodb", region_name=CONFIG.region).Table(
                CONFIG.jobs_table
            )
        self._table = table

    # --- jobs ---
    def create(self, job: Job) -> None:
        self._table.put_item(Item=_to_item(job))

    def get(self, job_id: str) -> Job | None:
        resp = self._table.get_item(Key={"pk": f"JOB#{job_id}"})
        item = resp.get("Item")
        return _from_item(item) if item else None

    def update_status(self, job_id: str, status: JobStatus) -> None:
        self._table.update_item(
            Key={"pk": f"JOB#{job_id}"},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status.value},
        )

    def save(self, job: Job) -> None:
        self._table.put_item(Item=_to_item(job))

    # --- daily cap ---
    def reserve_daily_slot(self, day: str, limit: int | None = None) -> int:
        """Atomically increment today's counter; raise if over the cap.

        Returns the post-increment count. Uses a conditional update so concurrent
        Lambdas can't blow past the cap.
        """
        limit = limit if limit is not None else CONFIG.max_runs_per_day
        try:
            resp = self._table.update_item(
                Key={"pk": f"COUNTER#{day}"},
                UpdateExpression="SET #c = if_not_exists(#c, :zero) + :one, #t = :ttl",
                ConditionExpression="attribute_not_exists(#c) OR #c < :limit",
                ExpressionAttributeNames={"#c": "count", "#t": "ttl"},
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":one": 1,
                    ":limit": limit,
                    ":ttl": int(time.time()) + 2 * 86400,
                },
                ReturnValues="UPDATED_NEW",
            )
            return int(resp["Attributes"]["count"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DailyCapReached(f"daily cap of {limit} runs reached") from exc
            raise


def _to_item(job: Job) -> dict[str, Any]:
    item = job.model_dump(mode="json")
    item["pk"] = f"JOB#{job.job_id}"
    return item


def _from_item(item: dict[str, Any]) -> Job:
    data = {k: v for k, v in item.items() if k != "pk"}
    return Job.model_validate(data)
