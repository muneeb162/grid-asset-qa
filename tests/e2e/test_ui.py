"""End-to-end tests: a real browser against a real server, simulating what an operator does.

Kept deliberately few (testing pyramid): they are slow and cover only the critical user journeys.
"""
from __future__ import annotations

import re
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from app.main import create_app

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server() -> str:
    """Start a fresh server per test so every journey begins with an empty register."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("Test server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def add_asset(page: Page, name: str, voltage: str = "10", lat: str = "51.4888", lon: str = "7.5147",
              asset_type: str = "transformer") -> None:
    page.get_by_label("Name").fill(name)
    page.get_by_label("Type").select_option(asset_type)
    page.get_by_label("Voltage (kV)").fill(voltage)
    page.get_by_label("Latitude").fill(lat)
    page.get_by_label("Longitude").fill(lon)
    page.get_by_label("Commissioned on").fill("2015-06-01")
    page.get_by_role("button", name="Add asset").click()


def row(page: Page, name: str):
    return page.get_by_test_id("asset-row").filter(has_text=name)


# TC-030
def test_empty_register_invites_first_asset(page: Page, live_server: str):
    page.goto(live_server)
    expect(page.get_by_test_id("empty-state")).to_have_text("No assets yet. Add the first one with the form.")


# TC-031
def test_operator_adds_asset_and_sees_it_listed(page: Page, live_server: str):
    page.goto(live_server)

    add_asset(page, "TR Hoerde 04", voltage="10")

    expect(page.get_by_test_id("form-msg")).to_have_text("Added TR Hoerde 04.")
    new_row = row(page, "TR Hoerde 04")
    expect(new_row).to_contain_text("10 kV")
    expect(new_row).to_contain_text("medium")
    expect(new_row.get_by_test_id("status-badge")).to_have_text("In service")
    expect(page.get_by_test_id("count-in_service")).to_have_text("1")
    expect(page.get_by_label("Name")).to_have_value("")  # form is cleared for the next entry


# TC-032
def test_invalid_coordinates_show_field_error_and_keep_input(page: Page, live_server: str):
    page.goto(live_server)

    add_asset(page, "Paris Substation", lat="48.8566", lon="2.3522")

    message = page.get_by_test_id("form-msg")
    expect(message).to_contain_text("Validation failed")
    expect(message).to_contain_text("longitude")
    expect(page.get_by_label("Name")).to_have_value("Paris Substation")  # user does not lose their input
    expect(page.get_by_test_id("empty-state")).to_be_visible()


# TC-033
def test_duplicate_name_shows_conflict_message(page: Page, live_server: str):
    page.goto(live_server)
    add_asset(page, "Cable K12", asset_type="cable")
    expect(row(page, "Cable K12")).to_be_visible()

    add_asset(page, "cable k12", asset_type="cable")

    expect(page.get_by_test_id("form-msg")).to_have_text(re.compile("already exists"))
    expect(page.get_by_test_id("asset-row")).to_have_count(1)


# TC-034: full outage lifecycle, the most important operator journey
def test_report_and_resolve_outage(page: Page, live_server: str):
    page.goto(live_server)
    add_asset(page, "UW Phoenix", voltage="110", asset_type="substation")
    target = row(page, "UW Phoenix")
    expect(target).to_contain_text("high")

    target.get_by_role("button", name="Report outage").click()
    dialog = page.get_by_test_id("outage-dialog")
    expect(dialog).to_be_visible()
    dialog.get_by_label("What happened?").fill("Busbar fault after storm")
    dialog.get_by_role("button", name="Report outage").click()

    expect(dialog).to_be_hidden()
    expect(target.get_by_test_id("status-badge")).to_have_text("Out of service")
    expect(page.get_by_test_id("count-out_of_service")).to_have_text("1")

    target.get_by_role("button", name="Mark resolved").click()

    expect(page.get_by_test_id("list-msg")).to_have_text("Outage resolved.")
    expect(target.get_by_test_id("status-badge")).to_have_text("In service")
    expect(page.get_by_test_id("count-out_of_service")).to_have_text("0")


# TC-035
def test_outage_dialog_rejects_too_short_description(page: Page, live_server: str):
    page.goto(live_server)
    add_asset(page, "TR 07")
    row(page, "TR 07").get_by_role("button", name="Report outage").click()
    dialog = page.get_by_test_id("outage-dialog")

    dialog.get_by_label("What happened?").fill("bad")
    dialog.get_by_role("button", name="Report outage").click()

    expect(dialog).to_be_visible()
    expect(page.get_by_test_id("outage-msg")).to_contain_text("description")
    expect(row(page, "TR 07").get_by_test_id("status-badge")).to_have_text("In service")


# TC-036
def test_status_filter(page: Page, live_server: str):
    page.goto(live_server)
    add_asset(page, "TR A")
    expect(row(page, "TR A")).to_be_visible()
    add_asset(page, "TR B")
    expect(row(page, "TR B")).to_be_visible()
    row(page, "TR B").get_by_role("button", name="Report outage").click()
    page.get_by_label("What happened?").fill("Oil leak detected")
    page.get_by_test_id("outage-dialog").get_by_role("button", name="Report outage").click()
    expect(row(page, "TR B").get_by_test_id("status-badge")).to_have_text("Out of service")

    page.get_by_test_id("status-filter").select_option("out_of_service")
    expect(page.get_by_test_id("asset-row")).to_have_count(1)
    expect(row(page, "TR B")).to_be_visible()

    page.get_by_test_id("status-filter").select_option("maintenance")
    expect(page.get_by_test_id("empty-state")).to_have_text("No assets with this status.")
