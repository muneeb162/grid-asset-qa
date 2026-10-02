# Test case specification

Each automated case is tagged with its ID in a comment above the test function, so any failing test can be traced back to this sheet and to its business rule (see `TEST_PLAN.md`, section 4).

Priority: **P1** blocks release, **P2** must be fixed soon, **P3** nice to have.

## Automated: API and unit

| ID | Title | Rule | Technique | Expected result | Prio | Location |
|---|---|---|---|---|---|---|
| TC-001 | Create a valid asset | | Positive | 201, id assigned, status `in_service`, voltage level derived | P1 | `api/test_assets_api.py` |
| TC-002 | Read back a created asset | | Positive | GET returns exactly what POST returned | P1 | `api/test_assets_api.py` |
| TC-003 | Reject duplicate name in any case | BR-01 | Equivalence classes | 409, nothing stored | P1 | `api/test_assets_api.py` |
| TC-004 | Every invalid field is named in the error | BR-02, 03, 04, 07 | Error guessing | 422, `errors[].field` names the bad field only | P1 | `api/test_assets_api.py` |
| TC-005 | Unknown asset id | | Negative | 404 with readable message | P2 | `api/test_assets_api.py` |
| TC-006 | Filter list by type and status | | Combinations | Each filter and the combination return the right subset | P2 | `api/test_assets_api.py` |
| TC-007 | Switch to maintenance and back | | State transition | 200, status updated each time | P2 | `api/test_assets_api.py` |
| TC-008 | Delete an asset | | Positive | 204, then 404 on read; ids are not reused | P2 | `api/test_assets_api.py` |
| TC-009 | GeoJSON coordinate order | | Error guessing | `[longitude, latitude]` per RFC 7946 | P1 | `api/test_assets_api.py` |
| TC-010 | Voltage level boundaries | BR-05 | Boundary values | 0.999 low, 1.0 medium, 59.999 medium, 60.0 high | P1 | `unit/test_validation.py` |
| TC-011 | Voltage out of range | BR-04 | Boundary values | 0, negative and above 380 kV rejected | P1 | `unit/test_validation.py` |
| TC-012 | Coordinates on the Germany boundary | BR-02 | Boundary values | All four corners accepted | P2 | `unit/test_validation.py` |
| TC-013 | Coordinates outside Germany | BR-02 | Boundary values | Rejected, error names latitude or longitude | P1 | `unit/test_validation.py` |
| TC-014 | Commissioning date today vs tomorrow | BR-03 | Boundary values | Today accepted, tomorrow rejected | P2 | `unit/test_validation.py` |
| TC-015 | Name length after trimming | | Boundary values | 2 rejected, 3 and 60 accepted, 61 rejected | P3 | `unit/test_validation.py` |
| TC-016 | Timezone normalisation | | Error guessing | CEST input stored as UTC | P2 | `unit/test_validation.py` |
| TC-020 | Report outage | BR-06 | State transition | Asset becomes `out_of_service` | P1 | `api/test_outages_api.py` |
| TC-021 | Second open outage on same asset | BR-06 | Negative | 409, still one outage | P1 | `api/test_outages_api.py` |
| TC-022 | Resolve outage | BR-08 | State transition | Asset returns to `in_service` | P1 | `api/test_outages_api.py` |
| TC-023 | Resolve at or before start time | BR-08 | Boundary values | 422 for equal and earlier timestamps, also across timezones | P1 | `api/test_outages_api.py` |
| TC-024 | Resolve twice | BR-08 | Negative | 409 | P2 | `api/test_outages_api.py` |
| TC-025 | Delete asset with open outage | BR-09 | Negative | 409, asset still exists | P1 | `api/test_outages_api.py` |
| TC-026 | Manual status change during outage | BR-10 | State transition | 409, status stays `out_of_service` | P1 | `api/test_outages_api.py` |
| TC-027 | Umlauts survive round trip | | Error guessing | "Umspannwerk Hörde" stored unchanged | P2 | `api/test_assets_api.py` |
| TC-028 | Duplicate check with German spelling | BR-01 | Error guessing | "Kreuzstraße" and "KREUZSTRASSE" treated as duplicates. Regression for DEF-001 | P1 | `api/test_assets_api.py` |

## Automated: end to end (browser)

| ID | Journey | Expected result | Prio |
|---|---|---|---|
| TC-030 | Open an empty register | Empty state invites the user to add the first asset | P3 |
| TC-031 | Add an asset | Row appears with level and status; counter updates; form clears | P1 |
| TC-032 | Submit coordinates outside Germany | Error names longitude; user input is kept | P1 |
| TC-033 | Submit a duplicate name | Conflict message; still one row | P2 |
| TC-034 | Report and resolve an outage | Badge and counters switch to Out of service and back | P1 |
| TC-035 | Outage description too short | Dialog stays open with error; status unchanged | P2 |
| TC-036 | Filter by status | Only matching rows; empty state when none match | P2 |

All in `tests/e2e/test_ui.py`.

## Manual acceptance tests (Anwendertests)

These check things automation judges poorly. Fill in **Result** and **Date** when you execute them.

| ID | Title | Preconditions | Steps | Expected result | Result | Date |
|---|---|---|---|---|---|---|
| TC-M01 | Keyboard-only operation | App running, mouse unused | 1. Tab through the form. 2. Add an asset with Enter. 3. Tab to Report outage, open with Enter, close with Escape. | Every control reachable; focus outline always visible; Escape closes the dialog | Not run | |
| TC-M02 | Mobile layout | Browser width 375 px | 1. Load the page. 2. Add an asset. 3. Scroll the table sideways. | Form stacks above table; only the table scrolls sideways, never the page | Not run | |
| TC-M03 | Error messages are understandable | App running | 1. Submit an empty form. 2. Read every message. | Each message says which field is wrong and why, without technical jargon | Not run | |
| TC-M04 | Double click on Add asset | App running | 1. Fill a valid form. 2. Double click Add asset quickly. | Asset created once; second request gets a duplicate message, not a second row | Not run | |
| TC-M05 | Status colours without colour vision | Chrome DevTools, Rendering, emulate achromatopsia | 1. Create assets in all three statuses. 2. Compare badges. | Status still readable from the badge text alone | Not run | |
| TC-M06 | GeoJSON in a real GIS viewer | Two or more assets created | 1. Save `/api/assets/geojson`. 2. Open it in geojson.io or QGIS. | Points appear at the right places in Germany | Not run | |
