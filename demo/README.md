# The hardest test suite I ever built — demo

Companion repo for the EuroPython 2026 talk
[*The hardest test suite I ever built — a pytest case study*](https://ep2026.europython.eu/session/the-hardest-test-suite-i-ever-built-a-pytest-case-study).

**The thesis:** the hardest test suite is made of the simplest tests — the
difficulty lives in the architecture around them. This repo is that thesis,
runnable. `carwatch/` simulates a computer-vision system watching cars on
parking-lot cameras (noisy on purpose: OCR typos, color confusion, delays);
`tests/` is a faithful reconstruction of the integration-test architecture
from a real production system.

> The production code is private. Nothing here is copied from it — the
> patterns were rebuilt from scratch on synthetic data. The war stories from
> the talk, however, are all true. Including the rickshaw.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and GNU make.

```
make demo         # green: the suite against the good model (~10 s)
make regression   # red: SAME tests, broken model 2.2-rc — this is the point
```

Both produce a self-contained HTML report in `reports/` (failures come with
a rendered camera frame — the evidence) and an aggregated `statistics.txt`.

## The architecture, mapped to the talk

| What the talk shows | Where it lives |
|---|---|
| Double parametrization (recording x vehicle) | `tests/conftest.py` — `pytest_generate_tests` |
| Tests run WHILE the recording plays (live/end) | `tests/conftest.py` — `pytest_collection_modifyitems` |
| Escalating search: find "this car" in the noise | `tests/conftest.py` — `first_sighting` |
| The trust spectrum: assert → warn → statistics | `tests/test_suite.py` |
| Hungarian matching, misses/extras/late | `carwatch/stats.py` — "10 s late = 1 typo" |
| Evidence in the report (frame per failure) | `tests/conftest.py` — `report` fixture |
| The system under test (simulator, not ML) | `carwatch/simulator.py` + `noise.py` |

Every scenario in `tests/cases/` proves one thing: `smoke` (hello world),
`missed-car` and `duplicate` (regressions the stats catch), `two-cars-same-moment`
(why matching beats comparing), `rickshaw` (a vehicle with no plates and a
newspaper where the plate should be), `empty` (no ghosts), `long-run` (the
hourglass tests that wait for the next car).

## Knobs

- `MODEL_VERSION` — `2.1` (default, good) or `2.2-rc` (broken; regressions on)
- `CARWATCH_SPEED` — playback acceleration, default `300` (1 s wall = 5 min recording)
- `uv run pytest tests --cases north-gate__smoke` — run selected cases only
