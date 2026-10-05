"""HTTP and validation tests for viewing and creating catalogue venues."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.schemas.venue import _time, parse_create, parse_update
from app.services.event_store import StoreError
from app.routes import venues as venue_routes

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

    def test_catalogue_list_and_name_search_boundaries(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[venue]
        ) as query:
            catalogue = self.client.get("/api/venues/catalogue")
            name_search = self.client.get("/api/venues?name=Hall")

        self.assertEqual(catalogue.status_code, 200)
        self.assertEqual(name_search.status_code, 200)
        self.assertIn("deleted_at=is.null", query.call_args_list[0].args[0])
        self.assertIn("order=venue_name.asc", query.call_args_list[0].args[0])
        self.assertIn("venue_name=ilike.*Hall*", query.call_args_list[1].args[0])

        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request"
        ) as query:
            missing = self.client.get("/api/venues")
            too_long = self.client.get("/api/venues?name=" + "v" * 101)

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(too_long.status_code, 400)
        query.assert_not_called()

    def test_create_reports_empty_database_response(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[]
        ):
            response = self.client.post("/api/venues", json=valid_venue())

        self.assertEqual(response.status_code, 503)

    def test_venue_permission_error_is_not_misreported_as_a_generic_failure(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=StoreError(503, code="42501")
        ):
            response = self.client.get("/api/venues/catalogue")

        self.assertEqual(response.status_code, 403)
        self.assertIn("permission", response.json["error"])

    def test_update_venue_writes_only_changed_fields(self):
        updated = {"venue_id": VENUE_ID, **valid_venue(capacity=300), "version": 2}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[updated]
        ) as query:
            response = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "capacity": 300})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["venue"], updated)
        self.assertEqual(query.call_args.kwargs["payload"], {"capacity": 300})
        self.assertEqual(query.call_args.kwargs["method"], "PATCH")
        self.assertIn("version=eq.1", query.call_args.args[0])

    def test_update_venue_returns_current_record_when_staff_form_is_stale(self):
        current = {"venue_id": VENUE_ID, **valid_venue(capacity=275), "version": 2}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[], [current]]
        ):
            response = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "capacity": 300})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["venue"], current)
        self.assertIn("redo your update", response.json["error"])

    def test_update_venue_rejects_invalid_or_empty_change_without_writing(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request"
        ) as query:
            response = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "capacity": 0})

        self.assertEqual(response.status_code, 400)
        self.assertIn("capacity", response.json["errors"])
        query.assert_not_called()

    def test_update_accepts_the_minimum_version_and_capacity(self):
        updated = {"venue_id": VENUE_ID, **valid_venue(capacity=1), "version": 2}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[updated]
        ):
            response = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "capacity": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["venue"]["capacity"], 1)

    def test_update_rejects_malformed_payload_unknown_field_and_invalid_identifier(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request"
        ) as query:
            malformed = self.client.patch(f"/api/venues/{VENUE_ID}", data="[]", content_type="application/json")
            unknown = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "made_up": "value"})
            invalid_id = self.client.patch("/api/venues/not-a-uuid", json={"version": 1, "capacity": 1})

        self.assertEqual(malformed.status_code, 400)
        self.assertIn("form", malformed.json["errors"])
        self.assertEqual(unknown.status_code, 400)
        self.assertIn("made_up", unknown.json["errors"])
        self.assertEqual(invalid_id.status_code, 404)
        query.assert_not_called()

    def test_update_reports_not_found_when_venue_is_deleted_during_a_stale_update(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[], []]
        ):
            response = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "capacity": 1})

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json["error"])

    def test_update_requires_sign_in(self):
        response = self.client.patch(f"/api/venues/{VENUE_ID}", json={"version": 1, "capacity": 1})
        self.assertEqual(response.status_code, 401)

    def test_deletion_check_shows_upcoming_event_conflicts(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        event = {"event_id": str(uuid4()), "event_name": "Product launch", "status": "confirmed", "start_datetime": "2030-01-01T09:00:00Z"}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[venue], [event]]
        ):
            response = self.client.get(f"/api/venues/{VENUE_ID}/deletion-check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["venue"], venue)
        self.assertEqual(response.json["events"], [event])

    def test_deletion_check_handles_invalid_deleted_and_unauthenticated_venues(self):
        self.assertEqual(self.client.get(f"/api/venues/{VENUE_ID}/deletion-check").status_code, 401)
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[]
        ) as query:
            invalid = self.client.get("/api/venues/not-a-uuid/deletion-check")
            deleted = self.client.get(f"/api/venues/{VENUE_ID}/deletion-check")

        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(deleted.status_code, 404)
        self.assertIn("already been deleted", deleted.json["error"])
        self.assertEqual(query.call_count, 1)

    def test_deletion_check_allows_no_upcoming_events(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[venue], []]
        ):
            response = self.client.get(f"/api/venues/{VENUE_ID}/deletion-check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["events"], [])

    def test_delete_venue_blocks_upcoming_events_and_returns_them(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        event = {"event_id": str(uuid4()), "event_name": "Product launch", "status": "confirmed", "start_datetime": "2030-01-01T09:00:00Z"}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[venue], [event]]
        ) as query:
            response = self.client.delete(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["events"], [event])
        self.assertIn("upcoming scheduled events", response.json["error"])
        self.assertEqual(query.call_count, 2)

    def test_delete_venue_soft_deletes_a_venue_without_upcoming_events(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[venue], [], [venue]]
        ) as query:
            response = self.client.delete(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["venue"], venue)
        self.assertIn("removed from the catalogue", response.json["message"])
        self.assertEqual(query.call_args.kwargs["method"], "PATCH")
        self.assertTrue(query.call_args.kwargs["return_representation"])
        self.assertIn("deleted_at", query.call_args.kwargs["payload"])
        self.assertIn("deleted_at=is.null", query.call_args.args[0])

    def test_delete_reports_a_reason_when_venue_is_already_deleted(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[]
        ):
            response = self.client.delete(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 404)
        self.assertIn("already been deleted", response.json["error"])

    def test_delete_reports_not_found_when_venue_is_removed_after_the_conflict_check(self):
        venue = {"venue_id": VENUE_ID, **valid_venue()}
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=[[venue], [], []]
        ):
            response = self.client.delete(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 404)
        self.assertIn("already been deleted", response.json["error"])

    def test_delete_rejects_invalid_id_and_unauthenticated_request(self):
        self.assertEqual(self.client.delete(f"/api/venues/{VENUE_ID}").status_code, 401)
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request"
        ) as query:
            response = self.client.delete("/api/venues/not-a-uuid")

        self.assertEqual(response.status_code, 404)
        query.assert_not_called()

    def test_delete_reports_a_database_foreign_key_conflict(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", side_effect=StoreError(503, code="23503")
        ):
            response = self.client.delete(f"/api/venues/{VENUE_ID}")

        self.assertEqual(response.status_code, 409)
        self.assertIn("still linked", response.json["error"])

    def test_upcoming_event_boundary_and_inactive_statuses(self):
        exact_start = datetime(2030, 1, 1, tzinfo=timezone.utc)
        with patch("app.routes.venues.datetime") as clock:
            clock.now.return_value = exact_start
            path = venue_routes.upcoming_event_path(VENUE_ID)

        self.assertIn("start_datetime=gte.2030-01-01T00%3A00%3A00%2B00%3A00", path)

        events = [
            {"event_id": "active", "status": "confirmed"},
            {"event_id": "cancelled", "status": "cancelled"},
            {"event_id": "completed", "status": "completed"},
            {"event_id": "rejected", "status": "rejected"},
            {"event_id": "blank", "status": None},
        ]
        with patch("app.routes.venues.supabase_request", return_value=events):
            conflicts = venue_routes.scheduled_upcoming_events(VENUE_ID, "user-token")

        self.assertEqual([event["event_id"] for event in conflicts], ["active", "blank"])


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

    def test_partial_update_validates_only_the_field_being_changed(self):
        record, version, errors = parse_update({"version": 4, "capacity": 350})
        self.assertEqual(errors, {})
        self.assertEqual(version, 4)
        self.assertEqual(record, {"capacity": 350})

    def test_update_requires_a_version_and_a_change(self):
        _, _, errors = parse_update({"version": 0})
        self.assertIn("version", errors)
        self.assertIn("form", errors)

    def test_update_accepts_all_fields_at_their_lower_and_upper_valid_boundaries(self):
        hours = {
            day: ({"closed": True} if day == "sunday" else {"open": "00:00", "close": "23:59"})
            for day in DAYS
        }
        payload = {
            "version": 1,
            "venue_name": "V" * 150,
            "capacity": 1,
            "postal_code": "000000",
            "block_number": "B" * 50,
            "street_name": "S" * 150,
            "building_name": "N" * 150,
            "unit_number": "U" * 50,
            "wheelchair_accessible": False,
            "blind_accessible": True,
            "accessibility_notes": "A" * 1000,
            "facilities": ["wifi", "wifi"],
            "supported_room_layouts": ["theatre"],
            "operating_hours": hours,
            "default_setup_minutes": 0,
            "default_turnaround_minutes": 0,
        }

        record, version, errors = parse_update(payload)

        self.assertEqual(errors, {})
        self.assertEqual(version, 1)
        self.assertEqual(record["venue_name"], "V" * 150)
        self.assertEqual(record["facilities"], ["wifi"])
        self.assertEqual(record["operating_hours"]["monday"], {"open": "00:00", "close": "23:59"})

    def test_update_rejects_values_immediately_outside_numeric_and_length_boundaries(self):
        cases = {
            "venue_name": "V" * 151,
            "block_number": "B" * 51,
            "street_name": "S" * 151,
            "building_name": "N" * 151,
            "unit_number": "U" * 51,
            "accessibility_notes": "A" * 1001,
            "capacity": 0,
            "default_setup_minutes": -1,
            "default_turnaround_minutes": -1,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                _, _, errors = parse_update({"version": 1, field: value})
                self.assertIn(field, errors)

    def test_update_rejects_missing_required_values_bad_types_and_unknown_fields(self):
        cases = {
            "venue_name": None,
            "block_number": "   ",
            "street_name": 12,
            "capacity": True,
            "postal_code": "12345a",
            "wheelchair_accessible": "yes",
            "blind_accessible": None,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                _, _, errors = parse_update({"version": 1, field: value})
                self.assertIn(field, errors)

        _, _, errors = parse_update({"version": "1", "not_a_venue_field": "x"})
        self.assertIn("version", errors)
        self.assertIn("not_a_venue_field", errors)

    def test_update_allows_optional_text_to_be_cleared(self):
        record, _, errors = parse_update({
            "version": 1,
            "building_name": None,
            "unit_number": "",
            "accessibility_notes": "   ",
        })

        self.assertEqual(errors, {})
        self.assertEqual(record, {
            "building_name": None,
            "unit_number": None,
            "accessibility_notes": None,
        })

    def test_update_validates_postal_choice_and_operating_hour_boundaries(self):
        invalid_hours = valid_venue()["operating_hours"]
        invalid_hours["monday"] = {"open": "08:00", "close": "08:00"}
        cases = {
            "postal_code": "1234567",
            "facilities": [],
            "supported_room_layouts": ["unknown_layout"],
            "operating_hours": invalid_hours,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                _, _, errors = parse_update({"version": 1, field: value})
                self.assertIn(field, errors)

    def test_update_rejects_non_list_choices_and_invalid_operating_hour_shapes(self):
        malformed_hours = valid_venue()["operating_hours"]
        malformed_hours["monday"] = {"open": "invalid", "close": "22:00"}
        cases = {
            "facilities": ["wifi", 7],
            "supported_room_layouts": "theatre",
            "operating_hours": malformed_hours,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                _, _, errors = parse_update({"version": 1, field: value})
                self.assertIn(field, errors)

        hours_missing_a_day = valid_venue()["operating_hours"]
        del hours_missing_a_day["sunday"]
        _, _, errors = parse_update({"version": 1, "operating_hours": hours_missing_a_day})
        self.assertIn("operating_hours", errors)

    def test_update_choice_and_operating_hour_edge_cases(self):
        whitespace_choice = {"version": 1, "facilities": ["   "]}
        _, _, errors = parse_update(whitespace_choice)
        self.assertIn("facilities", errors)

        extra_day_hours = valid_venue()["operating_hours"]
        extra_day_hours["holiday"] = {"closed": True}
        _, _, errors = parse_update({"version": 1, "operating_hours": extra_day_hours})
        self.assertIn("operating_hours", errors)

        closed_day_hours = valid_venue()["operating_hours"]
        record, _, errors = parse_update({"version": 1, "operating_hours": closed_day_hours})
        self.assertEqual(errors, {})
        self.assertEqual(record["operating_hours"]["sunday"], {"closed": True})

        _, _, errors = parse_update({"version": 1, "operating_hours": "not an object"})
        self.assertIn("operating_hours", errors)

        invalid_schedule_hours = valid_venue()["operating_hours"]
        invalid_schedule_hours["monday"] = None
        _, _, errors = parse_update({"version": 1, "operating_hours": invalid_schedule_hours})
        self.assertIn("operating_hours", errors)

    def test_create_rejects_non_object_payload_and_time_parser_boundaries(self):
        _, errors = parse_create([])
        self.assertIn("form", errors)
        self.assertEqual(_time("00:00"), "00:00")
        self.assertIsNone(_time("24:00"))
        self.assertIsNone(_time(800))
