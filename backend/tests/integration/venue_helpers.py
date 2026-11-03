"""Shared setup and cleanup utilities for venue integration tests."""

from datetime import datetime, timedelta, timezone
import uuid

from tests.integration.supabase_admin import admin_request, delete_test_event


def future_window(days=120, hours=0, duration_hours=2):
    start = (datetime.now(timezone.utc) + timedelta(days=days, hours=hours)).replace(
        minute=0, second=0, microsecond=0,
    )
    return start, start + timedelta(hours=duration_hours)


def venue_payload(label=None, capacity=100):
    """A complete, valid catalogue payload, unique by name and address."""
    suffix = label or uuid.uuid4().hex[:8]
    hours = {
        day: {"open": "08:00", "close": "22:00"}
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    }
    return {
        "venue_name": f"ITEST Venue {suffix}",
        "capacity": capacity,
        "postal_code": "123456",
        "block_number": f"{suffix[:6]} Block",
        "street_name": "Integration Test Street",
        "building_name": "Integration Building",
        "unit_number": "#01-01",
        "wheelchair_accessible": True,
        "blind_accessible": True,
        "accessibility_notes": "Step-free entrance.",
        "facilities": ["projector"],
        "supported_room_layouts": ["theatre"],
        "operating_hours": hours,
        "default_setup_minutes": 0,
        "default_turnaround_minutes": 0,
    }


def create_venue_for_setup(payload=None):
    """Insert a temporary suitable venue as setup, bypassing RLS only here."""
    rows = admin_request("/rest/v1/venues", payload or venue_payload())
    assert len(rows) == 1, rows
    return rows[0]


def remove_venue_scenario(events, venues):
    """Remove bookings before their events and finally the temporary venues."""
    for event in events:
        admin_request(f"/rest/v1/venue_booking_requests?event_id=eq.{event['event_id']}", method="DELETE")
        delete_test_event(event)
    for venue in venues:
        admin_request(f"/rest/v1/venues?venue_id=eq.{venue['venue_id']}", method="DELETE")
