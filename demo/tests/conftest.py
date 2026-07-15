"""The architecture around the tests — this is where the difficulty lives.

- double parametrization: recording scope x vehicle scope (pytest_generate_tests)
- live/end orchestration: tests run WHILE the recording plays (collection_modifyitems)
- escalating search: find "this car" among noisy sightings (first_sighting)
- evidence: every visual check attaches the camera frame to the HTML report
"""

from __future__ import annotations

import base64
import itertools
import json
import time
from collections import defaultdict
from pathlib import Path

import pytest
from pytest_html import extras as html_extras

from carwatch.model import RecordingCase, VehicleCase
from carwatch.simulator import RecordingPlayer, speed
from carwatch.stats import edit_distance
from carwatch.store import EventStore

TESTS_PATH = Path(__file__).parent
RUNTIME_PATH = TESTS_PATH.parent / ".runtime"

SEARCH_TOLERANCE_MS = 60_000


# --- double parametrization ------------------------------------------------


def pytest_addoption(parser):
    parser.addoption("--cases", nargs="*", default=None, help="case ids to run")


def load_cases(selected):
    recording_cases, vehicle_cases = [], []
    for path in sorted((TESTS_PATH / "cases").glob("*.json")):
        raw = json.loads(path.read_text())
        case = RecordingCase(**raw)
        if selected and case.case_id not in selected:
            continue
        recording_cases.append(case)
        vehicle_cases.extend(
            VehicleCase(**raw, current=vehicle) for vehicle in case.all_vehicles
        )
    return recording_cases, vehicle_cases


def id_from_vehicle_case(case: VehicleCase) -> str:
    return f"{case.case_id}__{case.current.plate or 'no-plate'}"


def id_from_recording_case(case: RecordingCase) -> str:
    return case.case_id


def pytest_generate_tests(metafunc):
    recording_cases, vehicle_cases = load_cases(metafunc.config.getoption("--cases"))
    if "vehicle_case" in metafunc.fixturenames:
        metafunc.parametrize(
            "vehicle_case", vehicle_cases, ids=id_from_vehicle_case, indirect=True
        )
    if "recording_case" in metafunc.fixturenames:
        metafunc.parametrize(
            "recording_case", recording_cases, ids=id_from_recording_case, indirect=True
        )


@pytest.fixture(scope="session")
def vehicle_case(request) -> VehicleCase:
    return request.param


@pytest.fixture(scope="session")
def recording_case(request) -> RecordingCase:
    return request.param


# --- live/end orchestration --------------------------------------------------
# A recording plays ONCE; tests that can run while it plays ("live") go first,
# tests that need the full picture wait for the marker fixture recording_stopped.


@pytest.fixture
def recording_stopped():
    pass  # empty on purpose: its presence in a signature marks an "end" test


def pytest_collection_modifyitems(session, config, items):
    grouped = defaultdict(lambda: {"live": [], "end": []})
    other_tests = []
    for item in items:
        if not hasattr(item, "callspec"):
            other_tests.append(item)
            continue
        params = item.callspec.params
        case = params.get("vehicle_case") or params.get("recording_case")
        phase = "end" if "recording_stopped" in item.fixturenames else "live"
        grouped[case.recording][phase].append(item)

    items[:] = list(
        itertools.chain(
            *[[*group["live"], *group["end"]] for group in grouped.values()],
            other_tests,
        )
    )


# --- the world under test ----------------------------------------------------


@pytest.fixture(scope="session")
def event_store() -> EventStore:
    db_path = RUNTIME_PATH / "events.db"
    if db_path.exists():
        db_path.unlink()
    return EventStore(db_path)


@pytest.fixture(scope="session")
def start_recording(event_store):
    players: dict[str, RecordingPlayer] = {}

    def _start(case: RecordingCase) -> None:
        if case.recording in players:
            return
        for player in players.values():  # one recording at a time — like production
            player.join(timeout=120)
        player = RecordingPlayer(case, event_store, RUNTIME_PATH / "frames")
        players[case.recording] = player
        player.start()
        assert _wait_until(
            lambda: event_store.find(case.recording, ["TRACE"], "recording_started"),
            timeout_s=10,
        ), f"Recording {case.recording} did not start"

    yield _start
    for player in players.values():
        player.join(timeout=120)


def _wait_until(predicate, timeout_s, sleep_s=0.02):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(sleep_s)
    return False


def _recording_finished(case: RecordingCase, event_store: EventStore) -> bool:
    return bool(event_store.find(case.recording, ["TRACE"], "recording_finished"))


def _remaining_playback_s(case: RecordingCase, event_store: EventStore) -> float:
    if _recording_finished(case, event_store):
        return 0.3  # it's all in the store already — don't wait for the past
    played_ms = event_store.last_frame_time(case.recording)
    return max(0.5, (case.duration_ms - played_ms) / 1000 / speed()) + 2


# --- escalating search: find "this car" among noisy sightings ----------------

_sightings_cache: dict = {}


def _search_candidates(event_store, case: VehicleCase, claimed: set):
    rows = event_store.find(case.recording, ["POST"])
    return [
        row
        for row in rows
        if row["id"] not in claimed
        and row["direction"] == case.current.direction
        and abs(row["frame_time"] - case.current.appear_at) <= SEARCH_TOLERANCE_MS
    ]


def _by_plate(tolerance):
    def search(event_store, case, claimed):
        candidates = [
            row
            for row in _search_candidates(event_store, case, claimed)
            if edit_distance(row["plate"], case.current.plate) <= tolerance
        ]
        candidates.sort(
            key=lambda row: (
                edit_distance(row["plate"], case.current.plate),
                abs(row["frame_time"] - case.current.appear_at),
            )
        )
        return candidates[0] if candidates else None

    return search


def _by_time(event_store, case, claimed):
    candidates = [
        row
        for row in _search_candidates(event_store, case, claimed)
        # a tight window: a car 6 s away is somebody else's car, not a match
        if abs(row["frame_time"] - case.current.appear_at) <= 5_000
    ]
    candidates.sort(key=lambda row: abs(row["frame_time"] - case.current.appear_at))
    return candidates[0] if candidates else None


@pytest.fixture
def first_sighting(event_store, vehicle_case, start_recording) -> dict:
    cache_key = (vehicle_case.recording, vehicle_case.current)
    if cache_key in _sightings_cache:
        return _sightings_cache[cache_key]

    start_recording(vehicle_case)
    claimed = {row["id"] for row in _sightings_cache.values()}

    sighting = None
    for search in (_by_plate(1), _by_plate(2), _by_time):
        timeout_s = _remaining_playback_s(vehicle_case, event_store)  # recomputed
        sighting = _wait_until(
            lambda: search(event_store, vehicle_case, claimed),
            timeout_s=timeout_s if search is not _by_time else min(timeout_s, 1),
        )
        if sighting:
            break

    assert sighting, (
        f"No sighting found for {vehicle_case.current.plate or 'plateless vehicle'} "
        f"expected around t+{vehicle_case.current.appear_at / 1000:.1f}s"
    )
    _sightings_cache[cache_key] = sighting
    return sighting


@pytest.fixture
def last_update(event_store, vehicle_case, first_sighting, recording_stopped) -> dict:
    rows = event_store.find(
        vehicle_case.recording,
        ["POST", "PUT"],
        event_id=first_sighting["event_id"],
    )
    return rows[-1]


@pytest.fixture
def wait_for_recording_to_stop(event_store, recording_case, start_recording):
    start_recording(recording_case)
    finished = _wait_until(
        lambda: event_store.find(
            recording_case.recording, ["TRACE"], "recording_finished"
        ),
        timeout_s=_remaining_playback_s(recording_case, event_store) + 10,
    )
    assert finished, f"Recording {recording_case.recording} never finished"


# --- evidence: attach the camera frame to the HTML report --------------------


class Report:
    def __init__(self, extras_list):
        self._extras = extras_list

    def add_frame(self, sighting: dict) -> None:
        frame_src = sighting.get("frame_src")
        if not frame_src or not Path(frame_src).exists():
            return
        content = base64.b64encode(Path(frame_src).read_bytes()).decode()
        self._extras.append(html_extras.png(content))


@pytest.fixture
def report(extras) -> Report:
    return Report(extras)


@pytest.fixture(scope="session")
def reports_path() -> Path:
    path = TESTS_PATH.parent / "reports"
    path.mkdir(exist_ok=True)
    return path
