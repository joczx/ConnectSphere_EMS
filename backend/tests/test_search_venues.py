"""HTTP contract tests for the normal venue-name search."""

import unittest
from unittest.mock import patch
from urllib.parse import quote

from app import create_app

SEED_VENUE_NAMES = (
    "Suntec Singapore Convention Hall - Level 4",
    "Suntec Singapore Auditorium - Halls 602 to 604",
    "Singapore EXPO Hall 1",
    "Singapore EXPO Halls G, H and J",
    "Sands Grand Ballroom",
    "Fairmont Ballroom",
)


class VenueNameSearchTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_name_search_returns_matching_venues(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request",
            return_value=[{"venue_id": "venue-1", "venue_name": "Suntec Convention Hall"}],
        ) as query:
            response = self.client.get("/api/venues?name=Suntec")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertIn("venue_name=ilike.*Suntec*", query.call_args.args[0])

    def test_name_search_is_case_insensitive(self):
        venue = {"venue_id": "venue-1", "venue_name": "Suntec Convention Hall"}
        for name in ("suntec", "SUNTEC", "SuNtEc"):
            with self.subTest(name=name), patch(
                "app.routes.venues.authenticated_token", return_value="user-token"
            ), patch("app.routes.venues.supabase_request", return_value=[venue]) as query:
                response = self.client.get("/api/venues", query_string={"name": name})

            self.assertEqual(response.json, {"count": 1, "venues": [venue]})
            self.assertIn(f"venue_name=ilike.*{quote(name, safe='')}*", query.call_args.args[0])

    def test_every_seeded_venue_name_can_return_a_result(self):
        for index, name in enumerate(SEED_VENUE_NAMES, start=1):
            venue = {"venue_id": f"venue-{index}", "venue_name": name}
            with self.subTest(name=name), patch(
                "app.routes.venues.authenticated_token", return_value="user-token"
            ), patch("app.routes.venues.supabase_request", return_value=[venue]):
                response = self.client.get("/api/venues", query_string={"name": name})

            self.assertEqual(response.json, {"count": 1, "venues": [venue]})

    def test_nonexistent_venue_returns_an_empty_result_list(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"), patch(
            "app.routes.venues.supabase_request", return_value=[]
        ):
            response = self.client.get("/api/venues?name=NoSuchVenue")

        self.assertEqual(response.json, {"count": 0, "venues": []})

    def test_name_search_requires_text(self):
        with patch("app.routes.venues.authenticated_token", return_value="user-token"):
            response = self.client.get("/api/venues?name=")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "Enter a venue name to search."})

    def test_name_search_requires_sign_in(self):
        response = self.client.get("/api/venues?name=Suntec")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
