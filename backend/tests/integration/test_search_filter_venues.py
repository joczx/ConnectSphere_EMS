"""SCRUM-11: coordinator searches against isolated real catalogue fixtures.

AC1/2: dates, attendance/capacity, location, accessibility, layouts, facilities.
AC3: modified/removed criteria take effect on subsequent requests.
AC4: an empty result is returned for the UI's no-match message. Browser message
rendering is not covered. Time-of-day filtering is not supported by this API;
date filtering checks operating days, not bookings or hourly availability.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.supabase_admin import admin_request


@pytest.fixture(scope="module")
def catalogue():
    marker = f"ITEST-SCRUM-11-{uuid.uuid4().hex[:12]}"
    hours = {day: {"open": "08:00", "close": "22:00"} for day in (
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
    base = {
        "capacity": 100, "postal_code": "123456", "block_number": "1",
        "street_name": "Integration Street", "building_name": "North Test Building",
        "wheelchair_accessible": True, "blind_accessible": True,
        "facilities": ["projector", "wifi"], "supported_room_layouts": ["theatre"],
        "operating_hours": hours, "default_setup_minutes": 0, "default_turnaround_minutes": 0,
    }
    variants = {
        "matching": {},
        "small": {"capacity": 20},
        "alternative": {"building_name": "South Test Building", "wheelchair_accessible": False,
                        "blind_accessible": False, "facilities": ["wifi"],
                        "supported_room_layouts": ["banquet"]},
        "closed": {"operating_hours": {day: {"closed": True} for day in hours}},
        "deleted": {"deleted_at": datetime.now(timezone.utc).isoformat()},
    }
    rows = {}
    try:
        for label, changes in variants.items():
            row, = admin_request("/rest/v1/venues", {
                **base, **changes, "venue_name": f"{marker}-{label}"})
            rows[label] = row
        yield marker, rows
    finally:
        # Name-based cleanup also handles partially completed fixture setup.
        for row in admin_request(f"/rest/v1/venues?venue_name=like.{marker}*"):
            admin_request(f"/rest/v1/venues?venue_id=eq.{row['venue_id']}", method="DELETE")


@pytest.fixture
def search(client, sign_in, catalogue):
    marker, _ = catalogue
    headers = sign_in("Event Coordinator")

    def run(**criteria):
        response = client.get("/api/venues/search", headers=headers,
                              query_string={"name": marker, **criteria})
        assert response.status_code == 200, response.get_json()
        assert response.headers["Cache-Control"] == "no-store"
        body = response.get_json()
        assert body["count"] == len(body["venues"])
        return {row["venue_id"] for row in body["venues"]}

    return run


# TC-SFV-IT-001 (AC1,2): combined requirements leave exactly one match.
def test_combined_requirements_return_only_matching_venue(search, catalogue):
    _, rows = catalogue
    day = (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%d-%m-%Y")
    assert search(capacity="100", location="North", wheelchair_accessible="true",
                  blind_accessible="true", layouts=["theatre"], facilities=["projector", "wifi"],
                  start_date=day, end_date=day) == {rows["matching"]["venue_id"]}


# TC-SFV-IT-002 (AC1,2): individual filters exercise real query predicates.
@pytest.mark.parametrize("criteria,labels", [
    ({"capacity": "100"}, {"matching", "alternative", "closed"}),
    ({"capacity": "101"}, set()),
    ({"location": "south"}, {"alternative"}),
    ({"wheelchair_accessible": "true"}, {"matching", "small", "closed"}),
    ({"blind_accessible": "true"}, {"matching", "small", "closed"}),
    ({"layouts": ["banquet"]}, {"alternative"}),
    ({"layouts": ["banquet", "theatre"]}, {"matching", "small", "alternative", "closed"}),
    ({"facilities": ["projector", "wifi"]}, {"matching", "small", "closed"}),
])
def test_each_filter_selects_expected_venues(search, catalogue, criteria, labels):
    _, rows = catalogue
    assert search(**criteria) == {rows[label]["venue_id"] for label in labels}


# TC-SFV-IT-003 (AC1,2): every requested date needs a recorded operating day.
def test_date_range_excludes_closed_venues(search, catalogue):
    _, rows = catalogue
    start = datetime.now(timezone.utc).date() + timedelta(days=60)
    assert search(start_date=start.strftime("%d-%m-%Y"),
                  end_date=(start + timedelta(days=2)).strftime("%d-%m-%Y")) == {
                      rows[label]["venue_id"] for label in ("matching", "small", "alternative")}


# TC-SFV-IT-004 (AC3): changing/removing conditions recomputes results.
def test_criteria_can_be_modified_and_removed(search, catalogue):
    _, rows = catalogue
    assert search(layouts=["banquet"]) == {rows["alternative"]["venue_id"]}
    assert search(layouts=["theatre"]) == {rows[label]["venue_id"]
                                           for label in ("matching", "small", "closed")}
    assert search() == {row["venue_id"] for label, row in rows.items() if label != "deleted"}
    assert search(capacity="1000") == set()
    assert search(capacity="") == search()


# TC-SFV-IT-005 (AC4): no match is a successful empty search, not a server error.
def test_no_match_returns_zero_count_and_empty_venues(client, sign_in, catalogue):
    marker, _ = catalogue
    response = client.get("/api/venues/search", headers=sign_in("Event Coordinator"),
                          query_string={"name": marker, "capacity": "1000"})
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {"count": 0, "venues": []}


# TC-SFV-IT-006 (AC2): case-insensitive name search excludes deleted entries.
def test_name_search_is_case_insensitive(client, sign_in, catalogue):
    marker, rows = catalogue
    response = client.get("/api/venues", headers=sign_in("Event Coordinator"),
                          query_string={"name": marker.lower()})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["count"] == 4
    assert {row["venue_id"] for row in response.get_json()["venues"]} == {
        row["venue_id"] for label, row in rows.items() if label != "deleted"}


# TC-SFV-IT-007 (AC1): invalid criteria receive actionable field errors.
@pytest.mark.parametrize("criteria,field", [
    ({"capacity": "0"}, "capacity"),
    ({"capacity": "1.5"}, "capacity"),
    ({"start_date": "01-01-2030"}, "end_date"),
    ({"start_date": "02-01-2030", "end_date": "01-01-2030"}, "end_date"),
    ({"start_date": "invalid", "end_date": "01-01-2030"}, "start_date"),
    ({"layouts": ["invalid"]}, "layouts"),
    ({"facilities": ["invalid"]}, "facilities"),
    ({"wheelchair_accessible": "invalid"}, "wheelchair_accessible"),
])
def test_invalid_filters_return_field_errors(client, sign_in, criteria, field):
    response = client.get("/api/venues/search", headers=sign_in("Event Coordinator"),
                          query_string=criteria)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"] and field in response.get_json()["errors"]
    assert "venues" not in response.get_json()


def test_search_requires_authentication(client):
    response = client.get("/api/venues/search")
    assert response.status_code == 401, response.get_json()
    assert "venues" not in response.get_json()
