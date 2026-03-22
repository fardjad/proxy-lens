from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from proxylens_server.common.time import parse_rfc3339, to_rfc3339
from proxylens_server.infra.persistence.repositories.requests import RequestRepository


class HistogramBucket(StrEnum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"


class HistogramPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    request_count: int


class RequestHistogram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: HistogramBucket
    captured_after: str | None = None
    captured_before: str | None = None
    points: list[HistogramPoint]


class RequestHistogramInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    captured_after: str | None = None
    captured_before: str | None = None
    bucket: HistogramBucket | None = None
    max_points: int = Field(default=200, ge=1)


class RequestHistogramOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    histogram: RequestHistogram


class RequestHistogramUseCase:
    def __init__(self, request_repository: RequestRepository) -> None:
        self._request_repository = request_repository

    def execute(self, data: RequestHistogramInput) -> RequestHistogramOutput:
        captured_values = [
            request.captured_at for request in self._request_repository.list_summaries()
        ]
        filtered = [
            value
            for value in captured_values
            if self._time_in_range(
                value,
                captured_after=data.captured_after,
                captured_before=data.captured_before,
            )
        ]
        effective_bucket = self._effective_bucket(data)
        counts: dict[str, int] = {}
        for value in filtered:
            bucketed = self._bucket_timestamp(parse_rfc3339(value), effective_bucket)
            key = to_rfc3339(bucketed)
            counts[key] = counts.get(key, 0) + 1
        return RequestHistogramOutput(
            histogram=RequestHistogram(
                bucket=effective_bucket,
                captured_after=data.captured_after,
                captured_before=data.captured_before,
                points=[
                    HistogramPoint(timestamp=timestamp, request_count=request_count)
                    for timestamp, request_count in sorted(counts.items())
                ],
            )
        )

    def _time_in_range(
        self,
        value: str,
        *,
        captured_after: str | None,
        captured_before: str | None,
    ) -> bool:
        timestamp = parse_rfc3339(value)
        if captured_after is not None and timestamp <= parse_rfc3339(captured_after):
            return False
        if captured_before is not None and timestamp >= parse_rfc3339(captured_before):
            return False
        return True

    def _effective_bucket(self, data: RequestHistogramInput) -> HistogramBucket:
        if data.bucket is None:
            if data.captured_after is None or data.captured_before is None:
                return HistogramBucket.MINUTE
            seconds = max(
                1,
                int(
                    (
                        parse_rfc3339(data.captured_before)
                        - parse_rfc3339(data.captured_after)
                    ).total_seconds()
                ),
            )
            if seconds <= data.max_points:
                return HistogramBucket.SECOND
            if seconds / 60 <= data.max_points:
                return HistogramBucket.MINUTE
            return HistogramBucket.HOUR

        if data.captured_after is None or data.captured_before is None:
            return data.bucket

        seconds = max(
            1,
            int(
                (
                    parse_rfc3339(data.captured_before)
                    - parse_rfc3339(data.captured_after)
                ).total_seconds()
            ),
        )
        bucket_seconds = {
            HistogramBucket.SECOND: 1,
            HistogramBucket.MINUTE: 60,
            HistogramBucket.HOUR: 3600,
        }
        order = [HistogramBucket.SECOND, HistogramBucket.MINUTE, HistogramBucket.HOUR]
        current_index = order.index(data.bucket)
        while (
            seconds / bucket_seconds[order[current_index]] > data.max_points
            and current_index < len(order) - 1
        ):
            current_index += 1
        return order[current_index]

    def _bucket_timestamp(self, timestamp, bucket: HistogramBucket):
        if bucket == HistogramBucket.SECOND:
            return timestamp.replace(microsecond=0)
        if bucket == HistogramBucket.MINUTE:
            return timestamp.replace(second=0, microsecond=0)
        return timestamp.replace(minute=0, second=0, microsecond=0)
