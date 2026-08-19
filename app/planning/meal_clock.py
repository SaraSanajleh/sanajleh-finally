"""Per-day meal and day-span clocks — exploring days only (not arrival)."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.context.models import DayIntent
from app.planning.profile import TouristProfile

# Exploring-day windows (inclusive minute ranges).
BREAKFAST_RANGE = ((9, 0), (11, 30))
LUNCH_RANGE = ((13, 0), (16, 0))
DINNER_RANGE = ((19, 0), (22, 0))
DAY_START_RANGE = ((9, 0), (10, 0))
DAY_END_RANGE = ((22, 0), (23, 59))

MEAL_SLOT = {
    "breakfast": "morning",
    "lunch": "afternoon",
    "dinner": "evening",
}

MEAL_REASON = {
    "breakfast": "Breakfast in the morning, before visiting.",
    "lunch": "Lunch in the afternoon.",
    "dinner": "Dinner in the evening.",
}


@dataclass(frozen=True)
class ExploringDayClock:
    """Random-but-stable clock targets for one exploring day."""

    day_start: datetime
    breakfast_at: datetime
    lunch_at: datetime
    dinner_at: datetime
    morning_sights_end: datetime
    day_end: datetime

    def meal_target(self, label: str) -> datetime:
        return {
            "breakfast": self.breakfast_at,
            "lunch": self.lunch_at,
            "dinner": self.dinner_at,
        }[label]

    def meal_earliest(self, label: str) -> datetime:
        ranges = {
            "breakfast": BREAKFAST_RANGE,
            "lunch": LUNCH_RANGE,
            "dinner": DINNER_RANGE,
        }
        hour, minute = ranges[label][0]
        return datetime(2000, 1, 1, hour, minute)

    def meal_latest(self, label: str) -> datetime:
        ranges = {
            "breakfast": BREAKFAST_RANGE,
            "lunch": LUNCH_RANGE,
            "dinner": DINNER_RANGE,
        }
        hour, minute = ranges[label][1]
        return datetime(2000, 1, 1, hour, minute)


def _day_rng(profile: TouristProfile, intent: DayIntent) -> random.Random:
    key = (
        f"{profile.start_date}|{intent.day}|{intent.date}|"
        f"{','.join(profile.preferred_regions or [])}|{intent.region_key}"
    )
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _rand_clock(rng: random.Random, start: tuple[int, int], end: tuple[int, int]) -> datetime:
    start_m = start[0] * 60 + start[1]
    end_m = end[0] * 60 + end[1]
    pick = rng.randint(start_m, end_m)
    pick = (pick // 15) * 15
    return datetime(2000, 1, 1, pick // 60, pick % 60)


def build_exploring_day_clock(profile: TouristProfile, intent: DayIntent) -> ExploringDayClock:
    """Pick meal and day-span times inside fixed ranges; stable per trip/day."""
    rng = _day_rng(profile, intent)
    day_start = _rand_clock(rng, DAY_START_RANGE[0], DAY_START_RANGE[1])
    breakfast_at = _rand_clock(rng, BREAKFAST_RANGE[0], BREAKFAST_RANGE[1])
    breakfast_at = max(breakfast_at, day_start)
    lunch_at = _rand_clock(rng, LUNCH_RANGE[0], LUNCH_RANGE[1])
    dinner_at = _rand_clock(rng, DINNER_RANGE[0], DINNER_RANGE[1])
    day_end = _rand_clock(rng, DAY_END_RANGE[0], DAY_END_RANGE[1])
    morning_sights_end = lunch_at - timedelta(minutes=15)
    return ExploringDayClock(
        day_start=day_start,
        breakfast_at=breakfast_at,
        lunch_at=lunch_at,
        dinner_at=dinner_at,
        morning_sights_end=morning_sights_end,
        day_end=day_end,
    )
