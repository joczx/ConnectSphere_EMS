"""HTTP and validation tests for viewing and creating catalogue venues."""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.schemas.venue import parse_create
from app.services.event_store import StoreError

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
VENUE_ID = str(uuid4())


def valid_venue(**overrides):
    venue = {
        "venue_name": "ConnectSphere Hall",
        "capacity": 250,
        "postal_code": "123456",
        "block_number": "10",
        "street_name": "Example Street",
        "building_name": "ConnectSphere Centre",
        "unit_number": "Level 2",
        "wheelchair_accessible": True,
        "blind_accessible": False,
        "accessibility_notes": "Step-free entrance.",
        "facilities": ["stage", "wifi"],
        "supported_room_layouts": ["theatre", "classroom"],
        "operating_hours": {
            day: ({"closed": True} if day == "sunday" else {"open": "08:00", "close": "22:00"})
            for day in DAYS
        },
        "default_setup_minutes": 60,
        "default_turnaround_minutes": 30,
    }
    venue.update(overrides)
    return venue


class VenueCatalogueRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_view_individual_venue_returns_all_characteristics(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[venue]
        ) as query:
            response = self.client.get(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"venue": venue})
        self.assertIn(f"venue_id=eq.{VENUE_ID}", query.call_args.args[0])
        self.assertEqual(query.call_args.kwargs["token"], "user-token")

    def test_view_individual_venue_rejects_invalid_id_without_querying_database(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request"
        ) as query:
            response = self.client.get("/api/venues/not-a-uuid")

        self.assertEqual(response.status_code, 404)
        query.assert_not_called()

    def test_view_individual_venue_returns_not_found_for_inaccessible_row(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[]
        ):
            response = self.client.get(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 404)

    def test_create_venue_stores_validated_record(self):
        created = {"venue_id": VENUE_ID, **valid_venue()}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[created]
        ) as query:
            response = self.client.post("/api/venues", json=valid_venue())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["venue"], created)
        self.assertEqual(query.call_args.kwargs["token"], "user-token")
        self.assertEqual(query.call_args.kwargs["payload"], valid_venue())

    def test_create_venue_rejects_invalid_details_without_writing(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request"
        ) as query:
            response = self.client.post("/api/venues", json=valid_venue(capacity=0, postal_code="123"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("capacity", response.json["errors"])
        self.assertIn("postal_code", response.json["errors"])
        query.assert_not_called()

    def test_create_venue_reports_database_duplicate(self):
        duplicate = StoreError(503, code="23505")
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=duplicate
        ):
            response = self.client.post("/api/venues", json=valid_venue())

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json["error"])

    def test_view_and_create_require_sign_in(self):
        self.assertEqual(self.client.get(f"/api/venues/{VENUE_ID}").status_code, 401)
        self.assertEqual(self.client.post("/api/venues", json=valid_venue()).status_code, 401)


class VenueCreateSchemaTests(unittest.TestCase):
    def test_valid_venue_is_cleaned(self):
        record, errors = parse_create(valid_venue(venue_name="  ConnectSphere   Hall  "))
        self.assertEqual(errors, {})
        self.assertEqual(record["venue_name"], "ConnectSphere Hall")

    def test_all_seven_operating_days_are_required(self):
        hours = valid_venue()["operating_hours"]
        del hours["sunday"]
        _, errors = parse_create(valid_venue(operating_hours=hours))
        self.assertIn("operating_hours", errors)

    def test_open_day_must_close_after_opening(self):
        hours = valid_venue()["operating_hours"]
        hours["monday"] = {"open": "22:00", "close": "08:00"}
        _, errors = parse_create(valid_venue(operating_hours=hours))
        self.assertIn("Monday", errors["operating_hours"])

    def test_unknown_facility_is_rejected(self):
        _, errors = parse_create(valid_venue(facilities=["wifi", "unknown_facility"]))
        self.assertIn("facilities", errors)

    def test_client_cannot_choose_venue_id(self):
        _, errors = parse_create({**valid_venue(), "venue_id": VENUE_ID})
        self.assertIn("venue_id", errors)
