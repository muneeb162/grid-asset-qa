# Grid Asset Register: test automation project

![tests](https://github.com/muneeb162/grid-asset-qa/actions/workflows/tests.yml/badge.svg)

A small register for electricity grid assets (transformers, cables, substations) with outage tracking and a GeoJSON export, built as the target for a layered test suite.

The application is deliberately small. **The tests, the test documentation and the CI pipeline are the point of this project.**

## At a glance

| | |
|---|---|
| Automated tests | 90 (33 unit, 50 API, 7 browser end to end) |
| Coverage | 99% line and branch, CI fails below 90% |
| Manual test cases | 6 acceptance cases in the test case sheet |
| Defects found and documented | 1 ([DEF-001](docs/defects/DEF-001.md)), fixed with a regression test |
| Fault injection | 3 of 3 planted defects caught |
| Stack | Python, pytest, Playwright, FastAPI, GitHub Actions |

## What is tested, and how

- **Unit tests** check every validation rule with boundary value analysis: 0.999 kV versus 1.0 kV, coordinates exactly on the edge of Germany, a commissioning date of today versus tomorrow.
- **API tests** check status codes, a consistent error format, and the outage state machine: an asset with an open outage cannot be deleted or switched back to service.
- **Browser tests** (Playwright) cover the critical operator journeys: add an asset, get a clear error, report and resolve an outage.
- **Manual acceptance tests** cover what automation judges poorly: keyboard use, mobile layout, how understandable the error messages are.
- **Domain-specific risks** get their own tests: swapped latitude and longitude in the GeoJSON export, German date formats, CET versus UTC, and German spelling in names.

Every automated test is tagged with a test case ID that links it to [the test case sheet](docs/TEST_CASES.md) and its business rule in [the test plan](docs/TEST_PLAN.md).

## A defect this suite found

Asset names must be unique regardless of case. A test using German spelling showed that "Trafo Kreuzstraße" and "TRAFO KREUZSTRASSE" were accepted as two different assets, because Python's `lower()` does not map ß to ss. The fix was one word (`casefold()`), and the test now guards against regression. Full report: [DEF-001](docs/defects/DEF-001.md).

## Do the tests actually catch bugs?

A suite that always passes proves little. `scripts/fault_injection.sh` plants three realistic defects one at a time and checks that a test fails for each:

```
CAUGHT   Swapped GeoJSON coordinates               by test_geojson_uses_longitude_latitude_order
CAUGHT   Off-by-one at the 60 kV boundary          by test_voltage_level_boundaries[60.0-high]
CAUGHT   Resolved outage does not restore status   by test_resolving_outage_returns_asset_to_service
```

## Run it

Requires Python 3.11 or newer.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m playwright install chromium

pytest -m smoke                       # critical paths in under a second
pytest -m "not e2e" --cov=app         # unit and API tests with coverage
pytest -m e2e                         # browser tests (add --headed to watch them)
pytest --html=reports/report.html     # everything, with an HTML report
./scripts/fault_injection.sh          # prove the suite catches planted bugs

uvicorn app.main:app --reload         # try the app at http://127.0.0.1:8000
```

## CI pipeline

GitHub Actions runs on every push, in two stages:

1. Smoke tests, then unit and API tests with the coverage gate
2. Playwright tests, only if stage 1 passed

Each run uploads a JUnit report, an HTML test report and a coverage report. Failed browser tests keep a Playwright trace and a screenshot.

## Project structure

```
app/
  models.py          validation rules (BR-02 to BR-05)
  service.py         business logic and outage state machine (BR-01, BR-06 to BR-10)
  main.py            REST API and consistent error format
  static/index.html  web UI used by the browser tests
tests/
  conftest.py        fixtures and test data builder
  unit/              validation and boundary tests
  api/               HTTP and state transition tests
  e2e/               Playwright browser tests
docs/
  TEST_PLAN.md       scope, levels, techniques, entry and exit criteria
  TEST_CASES.md      test case sheet: automated and manual
  defects/           defect reports and template
scripts/
  fault_injection.sh
.github/workflows/tests.yml
```
