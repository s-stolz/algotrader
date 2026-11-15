"""Daily wall-clock windows expressed as UTC candle timestamps."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SessionBounds:
    day_start_ms: int
    start_ms: int
    end_ms: int
    day_end_ms: int


@dataclass(frozen=True)
class SessionWindow:
    timezone: str = "UTC"
    start_minute: int = 0
    end_minute: int = 1440

    def __post_init__(self) -> None:
        ZoneInfo(self.timezone)
        if not 0 <= self.start_minute < self.end_minute <= 1440:
            raise ValueError("Session window must satisfy 0 <= start < end <= 1440")

    def bounds(self, timestamp_ms: int) -> SessionBounds:
        zone = ZoneInfo(self.timezone)
        day = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).astimezone(zone).date()
        return SessionBounds(
            day_start_ms=_local_timestamp(day, 0, zone),
            start_ms=_local_timestamp(day, self.start_minute, zone, validate=True),
            end_ms=_local_timestamp(day, self.end_minute, zone, validate=True),
            day_end_ms=_local_timestamp(day, 1440, zone),
        )


def _local_timestamp(day: date, minute: int, zone: ZoneInfo, validate: bool = False) -> int:
    wall_time = datetime.combine(day, time.min) + timedelta(minutes=minute)
    local = wall_time.replace(tzinfo=zone, fold=0)
    timestamp = int(local.timestamp() * 1000)
    if validate:
        restored = datetime.fromtimestamp(timestamp / 1000, timezone.utc).astimezone(zone)
        if restored.replace(tzinfo=None) != wall_time:
            raise ValueError(
                f"Session boundary {wall_time.isoformat()} does not exist in {zone.key}"
            )
    return timestamp
