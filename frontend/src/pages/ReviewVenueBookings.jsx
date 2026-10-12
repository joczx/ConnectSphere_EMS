import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { approvedOnly, pendingOnly } from '../components/BookingConflicts';
import { byStatus, statusLabel, venueBookingsApi, when } from '../services/venueBookings';

// Modelled on Review Event Requests: what has been received, then what has
// already been decided, each opening the request itself.
const SECTIONS = [
  ['Received', 'submitted', 'No booking requests are waiting for review.'],
  ['Approved', 'approved', null],
  ['Rejected', 'rejected', null],
];

// Enough to see from the queue which requests are already lost and which are
// contending for one slot; the request's own page names them.
function ConflictHint({ conflicts }) {
  const booked = approvedOnly(conflicts).length;
  const competing = pendingOnly(conflicts).length;
  if (booked) return <p className="booking-status booking-status-rejected">Venue already booked at this time</p>;
  if (competing) {
    return <p className="booking-status booking-status-submitted">
      {competing} other {competing === 1 ? 'request' : 'requests'} for this time
    </p>;
  }
  return null;
}

export default function ReviewVenueBookings() {
  const { api } = useAuth();
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    const controller = new AbortController();
    venueBookingsApi(api, '', { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setState({ data }); })
      .catch(err => {
        if (!controller.signal.aborted) setState({ error: err.message || 'Unable to load booking requests.' });
      });
    return () => controller.abort();
  }, [api]);

  const bookings = state.data?.bookings || [];

  return <>
    <Navbar />
    <main className="container">
      <Link to="/home">← Home</Link>
      <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Review venue bookings</h1></div></div>
      <p>All dates and times are in Singapore time (SGT).</p>
      {state.loading && <p role="status">Loading booking requests…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {/* Coordinators can read their own requests through the same endpoint,
          so the page says plainly that reviewing is not theirs to do. */}
      {state.data && !state.data.can_review && <div className="panel">
        <p>Only Venue Staff can review venue booking requests.</p>
        <Link to="/venue-bookings">See your own booking requests</Link>
      </div>}
      {state.data?.can_review && SECTIONS.map(([title, status, empty]) => {
        const items = byStatus(bookings, status);
        if (!items.length && !empty) return null;
        return <section key={status}>
          <h2>{title} <span className="metadata">({items.length})</span></h2>
          {!items.length && <p className="panel">{empty}</p>}
          <div className="event-list">{items.map(item => (
            <Link className="panel event-link" key={item.booking_id} to={'/review-venue-bookings/' + item.booking_id}>
              <h2>{item.event_name}</h2>
              <p>{item.venue_name}</p>
              <p className="metadata">{when(item.starts_at)} to {when(item.ends_at)} · {item.attendance} attending</p>
              <p className="metadata">
                Status: {statusLabel(item.status)}
                {item.status === 'submitted' ? ` · received ${when(item.submitted_at)}` : ` · ${when(item.reviewed_at)}`}
              </p>
              {status === 'submitted' && <ConflictHint conflicts={item.conflicts} />}
              <span>{status === 'submitted' ? 'Review request →' : 'View request →'}</span>
            </Link>
          ))}</div>
        </section>;
      })}
    </main>
  </>;
}
