"""UTC daily trading boundaries for declarative bar strategies."""

from collections.abc import Mapping
from dataclasses import dataclass

DAY_MS = 86_400_000
MINUTE_MS = 60_000


@dataclass(frozen=True)
class DailyTradingSchedule:
    entry_start_minute_utc: int
    last_entry_minute_utc: int
    exit_minute_utc: int

    def __post_init__(self) -> None:
        values = (
            self.entry_start_minute_utc,
            self.last_entry_minute_utc,
            self.exit_minute_utc,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("daily schedule boundaries must be integer UTC minutes")
        if not 0 <= values[0] < values[1] <= values[2] < 1440:
            raise ValueError("daily schedule requires 0 <= entry start < last entry <= exit < 1440")

    def allows_entry(self, timestamp_ms: int) -> bool:
        time_of_day = timestamp_ms % DAY_MS
        return (
            self.entry_start_minute_utc * MINUTE_MS
            <= time_of_day
            < self.last_entry_minute_utc * MINUTE_MS
        )

    def exit_timestamp(self, entry_timestamp_ms: int) -> int:
        return (entry_timestamp_ms // DAY_MS) * DAY_MS + self.exit_minute_utc * MINUTE_MS

    @classmethod
    def from_payload(cls, value: object) -> "DailyTradingSchedule | None":
        if value is None:
            return None
        fields = {"entry_start_minute_utc", "last_entry_minute_utc", "exit_minute_utc"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("daily_schedule must contain exactly the three UTC minute boundaries")
        return cls(**dict(value))
