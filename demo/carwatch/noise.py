"""Turns ground truth into what the "model" actually sees.

Noise is declarative and lives in the case file, so every case is reproducible
and proves exactly one thing. The `regressions` block is applied only when the
simulated model version is broken (MODEL_VERSION=2.2-rc) — same tests, worse
model, red report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from carwatch.model import ExpectedVehicle, RecordingCase

GOOD_MODEL = "2.1"
BROKEN_MODEL = "2.2-rc"

FIRST_READ_CORRECTION_MS = 1800  # a PUT with the corrected plate follows the POST
DUPLICATE_GAP_MS = 900


@dataclass
class Detection:
    """One emission of the system: what it saw and when."""

    request_type: str  # POST | PUT
    event_id: str
    plate: str
    color: str
    make: str
    direction: str
    frame_time: int  # ms, recording time
    vehicle_type: str = "car"
    ghost: bool = False  # the plate was read off something that isn't a plate


@dataclass
class Playback:
    detections: List[Detection] = field(default_factory=list)


def _first_read(vehicle: ExpectedVehicle, noise: dict) -> str:
    typos = noise.get("typos", {})
    ghost_reads = noise.get("ghost_reads", {})
    if vehicle.plate in ghost_reads:
        return ghost_reads[vehicle.plate]
    return typos.get(vehicle.plate, vehicle.plate)


def _seen_color(vehicle: ExpectedVehicle, noise: dict) -> str:
    return noise.get("color_confusion", {}).get(vehicle.plate, vehicle.color)


def render_playback(case: RecordingCase, model_version: str = GOOD_MODEL) -> Playback:
    noise = case.noise
    regressions = noise.get("regressions", {}) if model_version == BROKEN_MODEL else {}
    playback = Playback()

    for index, vehicle in enumerate(case.all_vehicles):
        if vehicle.plate in regressions.get("drop", []):
            continue  # the new model just... doesn't see this one

        delay = noise.get("delays_ms", {}).get(vehicle.plate, 300)
        delay += regressions.get("late_ms", {}).get(vehicle.plate, 0)
        event_id = f"{case.recording}#{index}"
        first_read = _first_read(vehicle, noise)
        is_ghost = vehicle.plate in noise.get("ghost_reads", {})

        playback.detections.append(
            Detection(
                request_type="POST",
                event_id=event_id,
                plate=first_read,
                color=_seen_color(vehicle, noise),
                make=vehicle.make,
                direction=vehicle.direction,
                frame_time=vehicle.appear_at + delay,
                vehicle_type=vehicle.vehicle_type,
                ghost=is_ghost,
            )
        )
        playback.detections.append(
            Detection(
                request_type="PUT",
                event_id=event_id,
                plate=vehicle.plate if not is_ghost else first_read,
                color=_seen_color(vehicle, noise),
                make=vehicle.make,
                direction=vehicle.direction,
                frame_time=vehicle.appear_at + delay + FIRST_READ_CORRECTION_MS,
                vehicle_type=vehicle.vehicle_type,
                ghost=is_ghost,
            )
        )

        if vehicle.plate in regressions.get("duplicate", []):
            playback.detections.append(
                Detection(
                    request_type="POST",
                    event_id=f"{event_id}-again",
                    plate=first_read,
                    color=_seen_color(vehicle, noise),
                    make=vehicle.make,
                    direction=vehicle.direction,
                    frame_time=vehicle.appear_at + delay + DUPLICATE_GAP_MS,
                    vehicle_type=vehicle.vehicle_type,
                )
            )

    order = noise.get("emit_order")
    if order:  # two cars in the same instant: the system picks its own order
        by_plate = {d.plate: [] for d in playback.detections}
        for d in playback.detections:
            by_plate.setdefault(d.plate, []).append(d)
        playback.detections = [d for plate in order for d in by_plate.get(plate, [])]
    else:
        playback.detections.sort(key=lambda d: d.frame_time)

    return playback
