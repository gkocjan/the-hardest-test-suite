"""The measuring instrument: match expected vehicles to received sightings.

Comparing sequences index-by-index breaks the moment two cars pass in the same
instant — so we don't compare, we MATCH. Every (expected, received) pair gets
a cost, scipy's linear_sum_assignment finds the globally optimal pairing, and
whatever is left unpaired becomes misses (expected, never seen) and extras
(seen, never expected). The exchange rate, as in the real system:
10 seconds of being late = 1 typo on the plate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
from scipy.optimize import linear_sum_assignment
from tabulate import tabulate

MAX_WEIGHT = 1_000_000_000_000
ON_TIME_MS = 2_000
MAX_EDIT_DISTANCE = 2
NO_PLATE_TIME_WINDOW_MS = 60_000


@dataclass(frozen=True)
class ExpectedRow:
    plate: str
    direction: str
    appear_at: int


@dataclass(frozen=True)
class ReceivedRow:
    first_plate: str
    last_plate: str
    direction: str
    frame_time: int


@dataclass(frozen=True)
class Matched:
    expected: ExpectedRow
    received: ReceivedRow

    @property
    def late_by_ms(self) -> int:
        return self.received.frame_time - self.expected.appear_at

    @property
    def was_too_late(self) -> bool:
        return self.late_by_ms > ON_TIME_MS


@dataclass
class Statistics:
    expected_count: int = 0
    misses: List[ExpectedRow] = field(default_factory=list)
    extras: List[ReceivedRow] = field(default_factory=list)
    late: List[Matched] = field(default_factory=list)
    matched: List[Matched] = field(default_factory=list)

    def __add__(self, other: "Statistics") -> "Statistics":
        return Statistics(
            expected_count=self.expected_count + other.expected_count,
            misses=self.misses + other.misses,
            extras=self.extras + other.extras,
            late=self.late + other.late,
            matched=self.matched + other.matched,
        )

    @property
    def accuracy(self) -> float:
        if not self.expected_count:
            return 1.0 if not self.extras else 0.0
        return (len(self.matched) - len(self.late)) / self.expected_count


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, l_char in enumerate(left, start=1):
        current = [i]
        for j, r_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (l_char != r_char),
                )
            )
        previous = current
    return previous[-1]


def _weight(expected: ExpectedRow, received: ReceivedRow) -> float:
    if expected.direction != received.direction:
        return MAX_WEIGHT

    time_difference = abs(received.frame_time - expected.appear_at)
    lateness = max(0, time_difference - ON_TIME_MS)

    if expected.plate == "" or received.last_plate == "":
        if time_difference > NO_PLATE_TIME_WINDOW_MS:
            return MAX_WEIGHT
        return lateness / 10_000  # matched purely by time — see: the rickshaw

    distance = edit_distance(expected.plate, received.last_plate)
    if distance > MAX_EDIT_DISTANCE:
        return MAX_WEIGHT

    return distance + lateness / 10_000  # 10 seconds = 1 edit distance


def calculate_misses_extras_and_late(
    expected: List[ExpectedRow], received: List[ReceivedRow]
) -> Statistics:
    stats = Statistics(expected_count=len(expected))
    if not expected or not received:
        stats.misses = list(expected)
        stats.extras = list(received)
        return stats

    cost = np.array([[_weight(e, r) for r in received] for e in expected])
    rows, columns = linear_sum_assignment(cost)

    paired_rows, paired_columns = set(), set()
    for row, column in zip(rows, columns):
        if cost[row][column] >= MAX_WEIGHT:
            continue
        paired_rows.add(row)
        paired_columns.add(column)
        match = Matched(expected=expected[row], received=received[column])
        stats.matched.append(match)
        if match.was_too_late:
            stats.late.append(match)

    stats.misses = [e for i, e in enumerate(expected) if i not in paired_rows]
    stats.extras = [r for i, r in enumerate(received) if i not in paired_columns]
    stats.matched.sort(key=lambda m: m.expected.appear_at)
    return stats


def summary_report(stats_by_recording: Dict[str, Statistics]) -> str:
    total = Statistics()
    rows = []
    for recording, stats in sorted(stats_by_recording.items()):
        total += stats
        rows.append(
            [
                recording,
                stats.expected_count,
                len(stats.matched),
                len(stats.misses),
                len(stats.extras),
                len(stats.late),
                f"{stats.accuracy:.0%}",
            ]
        )
    rows.append(
        [
            "TOTAL",
            total.expected_count,
            len(total.matched),
            len(total.misses),
            len(total.extras),
            len(total.late),
            f"{total.accuracy:.0%}",
        ]
    )
    return tabulate(
        rows,
        headers=["recording", "expected", "matched", "misses", "extras", "late", "acc"],
        tablefmt="github",
    )
