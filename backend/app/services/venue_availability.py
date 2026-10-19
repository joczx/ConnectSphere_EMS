"""Whether a venue is free for a period, given the bookings already approved.

Backs the "identify overlapping or conflicting venue bookings" story. Only an
approved booking makes a venue unavailable; pending requests may overlap.

The rule is the database's (027_venue_booking_conflicts.sql), which refuses a
conflicting request or approval outright. This module applies the same rule to
search results, so a booked venue is marked before anyone tries to request it.
The database decides which bookings clash, including each venue's setup and
turnaround time (040), so every booking returned here is a real conflict.
"""

from app.services.event_store import supabase_request


def approved_bookings(starts, ends, token):
    """Every approved booking overlapping a period, across all venues.

    Each is described by the database: the event is named only to Venue Staff
    and to the coordinator who made that request.
    """
    rows = supabase_request(
        '/rest/v1/rpc/venue_unavailability',
        token=token,
        payload={'p_starts': starts, 'p_ends': ends},
    )
    return rows if isinstance(rows, list) else []


def attach_conflicts(venues, bookings):
    """Copy each venue with the approved bookings that make it unavailable.

    A venue with any is no longer eligible, whatever it is like otherwise.
    Copied rather than changed in place, like event_venue_criteria.annotate().
    """
    marked = []
    for venue in venues:
        conflicts = [
            booking for booking in bookings
            if booking.get('venue_id') == venue.get('venue_id')
            and booking.get('status', 'approved') == 'approved'
        ]
        eligible = venue.get('eligible', True) and not conflicts
        marked.append({**venue, 'conflicts': conflicts, 'eligible': eligible})
    return marked


def mark_for_event(venues, event, token, ignore=None):
    """Search results for an event, marked with what is booked in its time.

    An event without a complete period cannot be checked, so nothing is marked
    rather than everything. `ignore` is a booking being modified, which must not
    count as a conflict with itself.
    """
    starts, ends = event.get('start_datetime'), event.get('end_datetime')
    if not starts or not ends:
        return [{**venue, 'conflicts': []} for venue in venues]
    bookings = [b for b in approved_bookings(starts, ends, token) if b.get('booking_id') != ignore]
    return attach_conflicts(venues, bookings)

