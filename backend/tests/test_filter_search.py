"""Unit tests for advanced venue filter search."""

import unittest
from unittest.mock import patch

from app import create_app
from app.schemas.venue_search import parse_filters
from app.services.venue_search_service import filter_search_path, matches_operating_hours


def valid_dates(**overrides):
    values = {
        "start_date": "21-09-2026",
        "end_date": "21-09-2026",
    }
    values.update(overrides)
    return values


class VenueFilterSearchTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_filter_search_passes_all_selected_filters_to_the_service(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.search_venues",
            return_value=[{"venue_id": "venue-1", "venue_name": "Singapore EXPO Hall 1"}],
        ) as search:
            response = self.client.get(
                "/api/venues/search?name=Singapore&capacity=500&location=Expo&layouts=theatre"
                "&layouts=classroom&facilities=wifi&wheelchair_accessible=true"
            )

        self.assertEqual(response.status_code, 200)
        filters = search.call_args.args[0]
        self.assertEqual(filters["name"], "Singapore")
        self.assertEqual(filters["capacity"], 500)
        self.assertEqual(filters["location"], "Expo")
        self.assertEqual(filters["layouts"], ["theatre", "classroom"])
        self.assertEqual(filters["facilities"], ["wifi"])
        self.assertTrue(filters["wheelchair_accessible"])

    def test_filter_search_rejects_an_end_date_before_its_start_date(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.search_venues"
        ) as search:
            response = self.client.get(
                "/api/venues/search?start_date=02-10-2026&end_date=01-10-2026"
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.json["errors"])
        search.assert_not_called()

    def test_filter_search_rejects_negative_attendance(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.search_venues"
        ) as search:
            response = self.client.get("/api/venues/search?capacity=-500")

        self.assertEqual(response.status_code, 400)
        self.assertIn("capacity", response.json["errors"])
        search.assert_not_called()

    def test_database_query_combines_each_filter_condition(self):
        filters, errors = parse_filters(
            {
                "name": "Singapore EXPO", "capacity": "500", "location": "Expo Drive", "layouts": ["theatre", "classroom"],
                "facilities": ["wifi", "stage"], "wheelchair_accessible": "true",
                "blind_accessible": "true", **valid_dates(),
            }
        )

        self.assertEqual(errors, {})
        path = filter_search_path(filters)
        for condition in (
            "venue_name=ilike.*Singapore%20EXPO*", "capacity=gte.500", "venue_name.ilike.*Expo%20Drive*",
            "supported_room_layouts=ov.{theatre,classroom}", "facilities=cs.{wifi,stage}",
            "wheelchair_accessible=eq.true", "blind_accessible=eq.true",
        ):
            self.assertIn(condition, path)

    def test_multi_day_event_requires_every_selected_day_to_be_open(self):
        venue = {"operating_hours": {
            "monday": {"open": "00:00", "close": "23:59:59.999999"},
            "tuesday": {"open": "00:00", "close": "23:59:59.999999"},
        }}
        filters, errors = parse_filters(valid_dates(end_date="22-09-2026"))

        self.assertEqual(errors, {})
        self.assertTrue(matches_operating_hours(venue, filters))
        venue["operating_hours"]["tuesday"] = {"closed": True}
        self.assertFalse(matches_operating_hours(venue, filters))
