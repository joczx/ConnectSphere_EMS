// Everything about one venue booking request, and the decision on it.
//
// Shared by the coordinator's request page and the Venue Staff review page, so
// both sides read the same request the same way.

import BookingConflicts, { approvedOnly, pendingOnly } from './BookingConflicts';
import { statusLabel, when } from '../services/venueBookings';

const preserve = { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' };

// `linkFor` turns another booking into a link the reader may follow: the review
// page for Venue Staff, their own request page for a coordinator.
export default function VenueBookingDetails({ booking, linkFor }) {
  const pending = booking.status === 'submitted';
  const blocking = pending ? approvedOnly(booking.conflicts) : [];
  const competing = pending ? pendingOnly(booking.conflicts) : [];
  const blocked = booking.status === 'approved' ? pendingOnly(booking.conflicts) : [];

  return <>
    {/* Each of these means the request can only be rejected. They are worked
        out by the database, which refuses the approval for the same reasons. */}
    {pending && booking.venue_deleted && <section className="panel booking-conflict-panel" role="alert">
      <h2>This venue has been removed from the catalogue</h2>
      <p>A request for a removed venue can no longer be approved, only rejected.</p>
    </section>}

    {pending && booking.matches_event === false && <section className="panel booking-conflict-panel" role="alert">
      <h2>The event has changed since this was requested</h2>
      <p>
        Its date, time or expected attendance no longer match this request, so approving it would
        book the wrong period. It can only be rejected; the Event Coordinator can then request the
        venue again for the event as it is now.
      </p>
    </section>}

    {blocking.length > 0 && <section className="panel booking-conflict-panel" role="alert">
      <h2>The venue is already booked at this time</h2>
      <p>An approved booking overlaps this request, so this request can no longer be approved.</p>
      <BookingConflicts conflicts={blocking} linkFor={linkFor} />
    </section>}

    {competing.length > 0 && <section className="panel">
      <h2>Other requests for this venue at this time</h2>
      <p>These are still waiting too. Approving any one of them makes the venue unavailable to the others.</p>
      <BookingConflicts conflicts={competing} linkFor={linkFor} />
    </section>}

    {blocked.length > 0 && <section className="panel">
      <h2>Requests this booking now blocks</h2>
      <p>These overlap this approved booking, so they can only be rejected.</p>
      <BookingConflicts conflicts={blocked} linkFor={linkFor} />
    </section>}

    <article className="panel">
      <p className={`booking-status booking-status-${booking.status}`}>{statusLabel(booking.status)}</p>
      <dl>{[
        ['Venue', booking.venue_name],
        ['Event', booking.event_id ? `${booking.event_name} (#${booking.event_id})` : booking.event_name],
        ['Event status', booking.event_status],
        ['Requested by', booking.requested_by_name],
        ['Submitted', when(booking.submitted_at)],
        ['Start date and time', when(booking.starts_at)],
        ['End date and time', when(booking.ends_at)],
        ['Expected attendance', booking.attendance],
        ['Venue requirements', booking.venue_requirements],
        ['Reference', booking.booking_id],
      ].map(([label, value]) => <div key={label}>
        <dt>{label}</dt>
        <dd style={preserve}>{value ?? 'Not specified'}</dd>
      </div>)}</dl>
    </article>

    {booking.status !== 'submitted' && <section className="panel">
      <h2>Decision</h2>
      <dl>
        <div><dt>Outcome</dt><dd>{statusLabel(booking.status)}</dd></div>
        <div><dt>Decided by</dt><dd>{booking.reviewed_by_name || 'Not recorded'}</dd></div>
        <div><dt>Decided on</dt><dd>{when(booking.reviewed_at)}</dd></div>
        <div><dt>Comments from Venue Staff</dt><dd style={preserve}>{booking.review_comments || 'No comments'}</dd></div>
      </dl>
    </section>}
  </>;
}
