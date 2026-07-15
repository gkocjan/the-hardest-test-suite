"""The hardest test suite — and every test in it is simple. That's the point.

The trust spectrum, top to bottom:
  hard assert  -> direction, timing, plate (with tolerance)
  warning      -> color, make (too nondeterministic to fail the build)
  statistics   -> misses / extras / late, matched by the Hungarian algorithm
  report       -> one aggregated summary at the very end
"""

import warnings
from collections import defaultdict

import pytest
from pytest_check import check
from pytest_harvest import get_fixture_store

from carwatch.stats import (
    ExpectedRow,
    ReceivedRow,
    Statistics,
    calculate_misses_extras_and_late,
    edit_distance,
    summary_report,
)

# --- live: these run while the recording is still playing --------------------


def test_start_recording(start_recording, recording_case):
    start_recording(recording_case)


def test_vehicle_appeared_on_time(vehicle_case, first_sighting):
    late_by_s = (first_sighting["frame_time"] - vehicle_case.current.appear_at) / 1000
    # no abs() here — being EARLY is the system getting better, not a bug
    assert (
        first_sighting["frame_time"] - vehicle_case.current.appear_at < 2000
    ), f"Vehicle was late by {late_by_s:.1f}s"


def test_vehicle_has_correct_plate(vehicle_case, first_sighting, report):
    if vehicle_case.current.plate == "":
        pytest.skip("vehicle without plates — ask us about the rickshaw")
    report.add_frame(first_sighting)
    distance = edit_distance(first_sighting["plate"], vehicle_case.current.plate)
    assert distance <= 1, (
        f"Expected {vehicle_case.current.plate}, read {first_sighting['plate']}"
    )


def test_vehicle_has_correct_color(vehicle_case, first_sighting, report):
    report.add_frame(first_sighting)
    if first_sighting["color"] != vehicle_case.current.color:
        warnings.warn(
            f"Wrong color: expected {vehicle_case.current.color}, "
            f"saw {first_sighting['color']}"
        )


def test_vehicle_has_correct_make(vehicle_case, first_sighting):
    if first_sighting["make"] != vehicle_case.current.make:
        warnings.warn(
            f"Wrong make: expected {vehicle_case.current.make}, "
            f"saw {first_sighting['make']}"
        )


def test_vehicle_has_correct_direction(vehicle_case, first_sighting):
    assert first_sighting["direction"] == vehicle_case.current.direction


# --- end: these wait for the whole recording ---------------------------------


def test_wait_for_recording_stop(wait_for_recording_to_stop, recording_stopped):
    pass  # an hourglass, not a test: it spends the tail of the recording


def test_only_one_sighting_per_vehicle(
    vehicle_case, first_sighting, event_store, recording_stopped
):
    posts = event_store.find(
        vehicle_case.recording, ["POST"], event_id=first_sighting["event_id"]
    )
    assert len(posts) == 1


def test_last_update_has_correct_plate(vehicle_case, last_update, recording_stopped):
    if vehicle_case.current.plate == "":
        pytest.skip("vehicle without plates — ask us about the rickshaw")
    assert last_update["plate"] == vehicle_case.current.plate


def test_no_misses_extras_or_late(
    recording_case, event_store, recording_stopped, wait_for_recording_to_stop, results_bag
):
    by_event = defaultdict(list)
    for row in event_store.find(recording_case.recording, ["POST", "PUT"]):
        by_event[row["event_id"]].append(row)

    received = [
        ReceivedRow(
            first_plate=rows[0]["plate"],
            last_plate=rows[-1]["plate"],
            direction=rows[0]["direction"],
            frame_time=rows[0]["frame_time"],
        )
        for rows in by_event.values()
    ]
    expected = [
        ExpectedRow(plate=v.plate, direction=v.direction, appear_at=v.appear_at)
        for v in recording_case.all_vehicles
    ]

    statistics = calculate_misses_extras_and_late(expected, received)
    results_bag.statistics = statistics
    results_bag.recording = recording_case.case_id

    with check:
        assert statistics.misses == [], f"{len(statistics.misses)} vehicles missed"
    with check:
        assert statistics.extras == [], f"{len(statistics.extras)} ghost sightings"
    with check:
        assert statistics.late == [], f"{len(statistics.late)} vehicles reported late"


def test_store_summary_report(request, reports_path):
    store = get_fixture_store(request)  # everything the results_bags collected
    stats_by_recording = {}
    for bag in store.get("results_bag", {}).values():
        if "statistics" in bag:
            stats_by_recording[bag["recording"]] = bag["statistics"]

    report = summary_report(stats_by_recording)
    (reports_path / "statistics.txt").write_text(report + "\n")
    print("\n" + report)

    total = sum(stats_by_recording.values(), Statistics())
    assert total.accuracy >= 0.90, f"Accuracy {total.accuracy:.0%} is below the 90% bar"
