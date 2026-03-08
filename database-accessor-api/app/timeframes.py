"""Timeframe code helpers for API routes."""

from enum import Enum


class TimeframeCode(str, Enum):
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"
    M10 = "M10"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    H12 = "H12"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


TIMEFRAME_TO_MINUTES: dict[TimeframeCode, int] = {
    TimeframeCode.M1: 1,
    TimeframeCode.M2: 2,
    TimeframeCode.M3: 3,
    TimeframeCode.M4: 4,
    TimeframeCode.M5: 5,
    TimeframeCode.M10: 10,
    TimeframeCode.M15: 15,
    TimeframeCode.M30: 30,
    TimeframeCode.H1: 60,
    TimeframeCode.H4: 240,
    TimeframeCode.H12: 720,
    TimeframeCode.D1: 1440,
    TimeframeCode.W1: 10080,
    TimeframeCode.MN1: 43200,
}


def timeframe_to_minutes(timeframe: TimeframeCode) -> int:
    return TIMEFRAME_TO_MINUTES[timeframe]
