"""Replays a recording in accelerated real time.

The system under test does not know it is watching the past: detections arrive
over wall-clock time (recording time / CARWATCH_SPEED), first guesses first,
corrections later. Tests poll the event store while the recording is playing.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from carwatch.frames import render_frame
from carwatch.model import RecordingCase
from carwatch.noise import GOOD_MODEL, render_playback
from carwatch.store import EventStore

DEFAULT_SPEED = 300  # 1 s of wall clock = 5 min of recording


def speed() -> int:
    return int(os.environ.get("CARWATCH_SPEED", DEFAULT_SPEED))


def model_version() -> str:
    return os.environ.get("MODEL_VERSION", GOOD_MODEL)


class RecordingPlayer(threading.Thread):
    def __init__(self, case: RecordingCase, store: EventStore, frames_dir: Path):
        super().__init__(name=f"player:{case.recording}", daemon=True)
        self.case = case
        self.store = store
        self.frames_dir = Path(frames_dir)
        self.playback = render_playback(case, model_version=model_version())

    def _sleep_until(self, frame_time_ms: int, started_at: float) -> None:
        target = started_at + frame_time_ms / 1000 / speed()
        delay = target - time.time()
        if delay > 0:
            time.sleep(delay)

    def run(self) -> None:
        started_at = time.time()
        self.store.insert(
            recording=self.case.recording,
            request_type="TRACE",
            event_type="recording_started",
        )

        for detection in self.playback.detections:
            self._sleep_until(detection.frame_time, started_at)
            frame_src = None
            if detection.request_type == "POST":
                frame_src = str(
                    render_frame(
                        self.frames_dir / f"{detection.event_id.replace('#', '_')}.png",
                        lot_name=self.case.lot_name,
                        camera=f"cam-{'entry' if detection.direction == 'IN' else 'exit'}",
                        frame_time_ms=detection.frame_time,
                        plate_read=detection.plate,
                        color_seen=detection.color,
                        vehicle_type=detection.vehicle_type,
                        ghost=detection.ghost,
                    )
                )
            self.store.insert(
                recording=self.case.recording,
                request_type=detection.request_type,
                event_id=detection.event_id,
                plate=detection.plate,
                color=detection.color,
                make=detection.make,
                direction=detection.direction,
                frame_time=detection.frame_time,
                frame_src=frame_src,
            )

        self._sleep_until(self.case.duration_ms, started_at)
        self.store.insert(
            recording=self.case.recording,
            request_type="TRACE",
            event_type="recording_finished",
        )
