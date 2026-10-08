import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { Alert, AlertDescription, AlertTitle } from '../components/Alert';
import VenueBookingDetails from '../components/VenueBookingDetails';
import BookingConflicts, { approvedOnly } from '../components/BookingConflicts';
import { useAuth } from '../auth/AuthContext';
import { venueBookingsApi } from '../services/venueBookings';

export default function ReviewVenueBooking() {
  const { api } = useAuth();
  const { bookingId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true });
  const [comments, setComments] = useState('');
  const [attempt, setAttempt] = useState({ busy: false, error: '', fieldError: '', unmet: [] });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    venueBookingsApi(api, '/' + encodeURIComponent(bookingId), { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setState({ data }); })
      .catch(err => {
        if (!controller.signal.aborted) setState({ error: err.message || 'Unable to load this booking request.' });
      });
    return () => controller.abort();
  }, [api, bookingId, location.key]);

  async function decide(outcome) {
    // Checked here too, so the reviewer is told before anything is sent. The
    // database refuses a reasonless rejection either way.
    if (outcome === 'rejected' && !comments.trim()) {
      setAttempt({ busy: false, error: '', fieldError: 'Enter a reason for rejecting this request. The Event Coordinator will see it.', unmet: [] });
      return;
    }
    const verb = outcome === 'approved' ? 'Approve' : 'Reject';
    if (!window.confirm(`${verb} this booking request? This cannot be changed afterwards.`)) return;

    setAttempt({ busy: true, error: '', fieldError: '', unmet: [] });
    try {
      const result = await venueBookingsApi(api, `/${encodeURIComponent(bookingId)}/review`, {
        method: 'POST', body: { outcome, comments },
      });
      // Reloaded rather than patched in place, so the page shows the decision
      // exactly as it was recorded.
      navigate('/review-venue-bookings/' + bookingId, { replace: true, state: { message: result.message } });
      setComments('');
      setAttempt({ busy: false, error: '', fieldError: '', unmet: [] });
    } catch (err) {
      setAttempt({
        busy: false,
        error: err.message || 'Unable to record this decision.',
        fieldError: err.details?.comments || '',
        unmet: err.data?.unmet_requirements || [],
        conflicts: err.data?.conflicts || [],
      });
    }
  }

  const booking = state.data?.booking;
  const pending = booking?.status === 'submitted';
  const shortfalls = booking?.current_shortfalls || [];
  // Either reason means the request can only be rejected; the database
  // refuses an approval for both, and the page says so before anyone tries.
  const booked = approvedOnly(booking?.conflicts).length > 0;

  return <>
    <Navbar />
    <main className="container">
      <Link to="/review-venue-bookings">← Review venue bookings</Link>
      <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>{booking?.event_name || 'Booking request'}</h1></div></div>
      {location.state?.message && <p role="status" className="panel venue-success">{location.state.message}</p>}
      {state.loading && <p role="status">Loading booking request…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}

      {booking && <VenueBookingDetails booking={booking} linkFor={item => '/review-venue-bookings/' + item.booking_id} />}

      {/* Worked out by the database from the event as it is now, which is what
          approval checks. Shown before the decision so it is not discovered in
          a refusal. */}
      {pending && shortfalls.length > 0 && <Alert variant="destructive" className="page-alert">
        <AlertTitle>This venue no longer meets the event’s requirements</AlertTitle>
        <AlertDescription>
          <p>The event has changed since this request was made, so it cannot be approved:</p>
          <ul>{shortfalls.map(item => <li key={item}>{item}</li>)}</ul>
          <p>Reject it with a reason so the Event Coordinator can request another venue.</p>
        </AlertDescription>
      </Alert>}

      {pending && state.data?.can_review && <form className="panel" onSubmit={(e) => e.preventDefault()}>
        <h2>Decide</h2>
        <fieldset disabled={attempt.busy}>
          {attempt.error && <div role="alert" className="error" style={{ marginBottom: '12px' }}>
            {attempt.error}
            {attempt.unmet.length > 0 && <ul>{attempt.unmet.map(item => <li key={item}>{item}</li>)}</ul>}
            <BookingConflicts conflicts={attempt.conflicts} linkFor={item => '/review-venue-bookings/' + item.booking_id} />
          </div>}
          <label>
            Comments for the Event Coordinator (required when rejecting)
            <textarea
              rows="4"
              maxLength={2000}
              value={comments}
              aria-invalid={!!attempt.fieldError}
              aria-describedby={attempt.fieldError ? 'review-comments-error' : undefined}
              onChange={(e) => { setComments(e.target.value); setAttempt(current => ({ ...current, fieldError: '' })); }}
            />
          </label>
          {attempt.fieldError && <p id="review-comments-error" className="error">{attempt.fieldError}</p>}
          <div className="heading">
            <button type="button" className="secondary" onClick={() => decide('rejected')}>Reject</button>
            <button type="button" disabled={shortfalls.length > 0 || booked} onClick={() => decide('approved')}>
              {attempt.busy ? 'Saving…' : 'Approve'}
            </button>
          </div>
        </fieldset>
      </form>}
    </main>
  </>;
}
