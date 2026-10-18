import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueBookingDetails from '../components/VenueBookingDetails';
import { approvedOnly } from '../components/BookingConflicts';
import { useAuth } from '../auth/AuthContext';
import { SAFETY_REVIEW_WARNING, underSafetyReview, venueBookingsApi } from '../services/venueBookings';

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

  // Cancels only this booking; the event and its other bookings stay active.
  async function cancel() {
    const warning = underSafetyReview(booking.event_status) ? `${SAFETY_REVIEW_WARNING} ` : '';
    if (!window.confirm(`${warning}Cancel this venue booking? This cannot be undone.`)) return;
    try {
      const result = await venueBookingsApi(api, `/${encodeURIComponent(bookingId)}/cancel`, { method: 'POST' });
      setState({ booking: { ...booking, ...result.booking } });
    } catch (err) {
      setState(current => ({ ...current, error: err.message }));
    }
  }

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
      {/* Modifying or cancelling touches only this booking; the event and its other bookings are untouched. */}
      {['submitted', 'approved'].includes(booking?.status) && underSafetyReview(booking.event_status)
        && <p className="panel venue-warning" role="alert">{SAFETY_REVIEW_WARNING}</p>}
      {['submitted', 'approved'].includes(booking?.status) && ['planning', 'pending_safety_checks'].includes(booking.event_status) && <p className="venue-page-actions">
        <Link className="button-link" to={`/venue-search?event_id=${booking.event_id}&booking_id=${booking.booking_id}`}>Change venue</Link>
        <Link className="button-link" to={`/venue-bookings?event_id=${booking.event_id}&venue_id=${booking.venue_id}&booking_id=${booking.booking_id}`}>Edit notes</Link>
        <button type="button" className="danger-button" onClick={cancel}>Cancel booking</button>
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
