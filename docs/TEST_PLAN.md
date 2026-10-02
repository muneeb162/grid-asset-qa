# Test plan: Grid Asset Register

## 1. Purpose

This plan describes how the Grid Asset Register is tested: what is in scope, which test levels are used, how test cases are designed, and when a build counts as releasable.

## 2. System under test

A small register for grid operators (Netzbetreiber) to record network assets and track outages.

| Component | Technology | Interface |
|---|---|---|
| REST API | Python, FastAPI, Pydantic | `/api/assets`, `/api/outages`, `/api/assets/geojson` |
| Web UI | HTML, vanilla JavaScript | `/` |
| GIS export | GeoJSON (RFC 7946) | `/api/assets/geojson` |

## 3. Scope

**In scope**

- Input validation for assets and outages (business rules BR-01 to BR-05)
- Outage lifecycle and the state rules that depend on it (BR-06 to BR-10)
- GeoJSON export correctness, especially coordinate order
- Critical operator journeys in the browser
- German-language data (umlauts, ß)

**Out of scope**

- Performance and load testing
- Authentication (the system has none)
- Persistence (the register is in memory by design)
- Browsers other than Chromium

## 4. Business rules under test

| ID | Rule |
|---|---|
| BR-01 | Asset names are unique, ignoring case and following German spelling (ß equals SS) |
| BR-02 | Asset coordinates must lie inside Germany (lat 47.27 to 55.06, lon 5.87 to 15.04) |
| BR-03 | Commissioning date cannot be in the future |
| BR-04 | Voltage must be greater than 0 and at most 380 kV |
| BR-05 | Voltage level: below 1 kV is low, 1 kV to below 60 kV is medium, 60 kV and above is high |
| BR-06 | Reporting an outage sets the asset to out of service; one open outage per asset |
| BR-07 | All error responses use one consistent format that names the invalid field |
| BR-08 | An outage is resolved once, and only at a time after it started; resolving restores service |
| BR-09 | An asset with an open outage cannot be deleted |
| BR-10 | An asset with an open outage cannot be switched back to service or maintenance manually |

## 5. Test levels (testing pyramid)

| Level | Tool | Count | Runs | Purpose |
|---|---|---|---|---|
| Unit | pytest | 33 | every push | Validation rules and boundaries, isolated from HTTP |
| API / integration | pytest, FastAPI TestClient | 50 | every push | HTTP status codes, error format, state transitions |
| End-to-end | Playwright (Chromium) | 7 | every push, after API stage passes | Critical operator journeys in a real browser |
| Manual acceptance | Test case sheet | 6 | before a release | Usability, accessibility, layout: things automation judges poorly |

Many fast tests at the bottom, few slow ones at the top. E2E tests only cover journeys whose failure an operator would notice directly.

## 6. Test design techniques

- **Boundary value analysis:** every numeric and date limit is tested on, just inside and just outside the boundary (for example 0.999 kV, 1.0 kV, 59.999 kV, 60.0 kV).
- **Equivalence partitioning:** one representative value per class (a household voltage, a distribution voltage, a transmission voltage).
- **State transition testing:** the outage lifecycle (in service, out of service, resolved, reported again) including forbidden transitions.
- **Error guessing:** known defect classes from the GIS domain, such as swapped latitude and longitude, German date formats, and timezone mix-ups between CET and UTC.

## 7. Test data

Each test builds its own data with `asset_payload()` in `tests/conftest.py` and gets a fresh application instance, so tests never depend on each other or on execution order. A guard test fails if the default test data itself ever becomes invalid.

## 8. Entry and exit criteria

**Entry:** the code builds and the smoke tests (`pytest -m smoke`) pass.

**Exit (releasable):**

- 100% of automated tests pass
- Line and branch coverage of `app/` at least 90% (enforced in CI)
- Fault injection: all planted defects are caught (`scripts/fault_injection.sh`)
- No open defect with severity High or Critical
- Manual acceptance cases executed and results recorded in `TEST_CASES.md`

## 9. Environments and CI

GitHub Actions (`.github/workflows/tests.yml`) runs in two stages:

1. Smoke tests, then the full unit and API suite with the coverage gate
2. Playwright E2E tests, only if stage 1 passed

Each run publishes a JUnit XML file, an HTML test report and a coverage report as build artifacts. Failed E2E tests also keep a Playwright trace and screenshot for debugging.

## 10. Risks

| Risk | Mitigation |
|---|---|
| E2E tests become flaky through timing | Playwright auto-waiting assertions (`expect`), no fixed sleeps, fresh server per test |
| Tests pass but would not catch real bugs | Fault injection script plants known defects and checks they are caught |
| Date-dependent tests break over time | Future-date tests are computed relative to today, never hard coded |
