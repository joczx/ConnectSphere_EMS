import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueBookingDetails from '../components/VenueBookingDetails';
import { approvedOnly } from '../components/BookingConflicts';
import { useAuth } from '../auth/AuthContext';
import { venueBookingsApi } from '../services/venueBookings';

// One of the coordinator's own booking requests, opened from Venue Bookings.
// Read through the same endpoint as the review page; the database decides
// that a coordinator may only open their own.
export default function VenueBooking() {
  const { api } = useAuth();
  const { bookingId } = useParams();
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    venueBookingsApi(api, '/' + encodeURIComponent(bookingId), { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setState({ booking: data.booking }); })
      .catch(err => {
        if (!controller.signal.aborted) setState({ error: err.message || 'Unable to load this booking request.' });
      });
    return () => controller.abort();
  }, [api, bookingId]);

  const booking = state.booking;

  return <>
    <Navbar />
    <main className="container">
      <Link to="/venue-bookings">← My venue booking requests</Link>
      <div className="heading"><div><p className="eyebrow">VENUE BOOKINGS</p><h1>{booking?.event_name || 'Booking request'}</h1></div></div>
      <p>All dates and times are in Singapore time (SGT).</p>
      {state.loading && <p role="status">Loading booking request…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {booking && <VenueBookingDetails booking={booking} linkFor={item => '/venue-bookings/' + item.booking_id} />}
      {booking?.event_id && <p>
        <Link to={`/events/${encodeURIComponent(booking.event_id)}`}>Open the event →</Link>
      </p>}
      {/* Rejected, or still waiting but no longer approvable (the slot was taken,
          the venue removed, or the event moved): either way this request will not
          get the venue, so the next step is offered here. */}
      {booking && (booking.status === 'rejected' || (booking.status === 'submitted' && (approvedOnly(booking.conflicts).length > 0
          || booking.venue_deleted || booking.matches_event === false)))
        && booking.event_id && booking.event_status === 'planning' && <p>
        <Link className="button-link" to={`/venue-search?event_id=${encodeURIComponent(booking.event_id)}`}>
          Find another venue for this event
        </Link>
      </p>}
    </main>
  </>;
}
