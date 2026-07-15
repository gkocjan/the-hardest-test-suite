# The hardest test suite I ever built

> The hardest test suite is made of the simplest tests — the difficulty lives in the
> architecture around them, not in the assertions.

Companion repository for the talk *The hardest test suite I ever built — a pytest case study*
([EuroPython 2026](https://ep2026.europython.eu/session/the-hardest-test-suite-i-ever-built-a-pytest-case-study)).

- **Talk page:** https://belazy.dev/talks/the-hardest-test-suite-i-ever-built/
- **Slides (live):** https://gkocjan.github.io/the-hardest-test-suite/slides/ — press **S** for speaker notes
- **Slides (local):** [`slides/index.html`](slides/index.html)
- **Written form of the talk:** [`slides/handout.html`](slides/handout.html)
- **Runnable demo:** [`demo/`](demo/)

## What this is

A real production system watched cars on parking-lot cameras with computer vision — noisy,
non-deterministic, running 24/7. Its integration suite was ~21 tests, most only a few lines
long. They looked trivial. Building them was the hardest testing work I've done, because all
the difficulty was pushed into the fixtures and collection hooks around them.

The production code is private. **Nothing here is copied from it** — the patterns were rebuilt
from scratch on a synthetic domain (`carwatch`). The war stories in the talk are all true.
Including the rickshaw.

## Demo — quickstart

Requires [uv](https://docs.astral.sh/uv/) and GNU make.

```bash
cd demo
make demo         # green: the suite against the good model (~10 s)
make regression   # red: the SAME tests against a broken model — this is the point
```

Both produce a self-contained HTML report in `demo/reports/` (each failure carries a rendered
camera frame — the evidence) and an aggregated `statistics.txt`. See [`demo/README.md`](demo/README.md)
for the full module-to-talk-point map and the knobs (`MODEL_VERSION`, `CARWATCH_SPEED`, case
selection).

## The techniques the talk walks through

| What the talk shows | Where it lives in the demo |
|---|---|
| Double parametrization (recording × vehicle) | `demo/tests/conftest.py` — `pytest_generate_tests` |
| Tests run *while* the recording plays (live/end ordering) | `demo/tests/conftest.py` — `pytest_collection_modifyitems` |
| Escalating search: find "this car" in the noise | `demo/tests/conftest.py` — `first_sighting` |
| The trust spectrum: assert → warn → statistics | `demo/tests/test_suite.py` |
| Hungarian matching; misses / extras / late | `demo/carwatch/stats.py` |
| Evidence in the report (a frame per failure) | `demo/tests/conftest.py` — `report` fixture |
| The system under test (a simulator, not ML) | `demo/carwatch/simulator.py` + `noise.py` |

## License & credits

Code and demo: [MIT](LICENSE). Slide images are third-party works under their own licenses —
see [`slides/CREDITS.md`](slides/CREDITS.md).
