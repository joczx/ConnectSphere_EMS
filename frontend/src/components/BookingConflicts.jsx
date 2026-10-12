// Bookings that overlap another, described the same way wherever they appear:
// search results, the request form, and both sides of a request's own page.
//
// The database decides how much is shown. The period always is, because that
// is what the reader acts on; the event is named only to Venue Staff and to
// whoever made that request, so anyone else reads "another event".

import { Link } from 'react-router-dom';
import { period, statusLabel } from '../services/venueBookings';

function describe(conflict) {
  if (!conflict.visible) return 'Another event';
  return conflict.event_id ? `${conflict.event_name} (#${conflict.event_id})` : conflict.event_name;
}

export default function BookingConflicts({ conflicts, linkFor }) {
  if (!conflicts?.length) return null;
  return <ul className="booking-conflicts">
    {conflicts.map(conflict => {
      const to = conflict.visible && linkFor ? linkFor(conflict) : null;
      return <li key={conflict.booking_id}>
        <strong>{period(conflict.starts_at, conflict.ends_at)}</strong>
        {' · '}{to ? <Link to={to}>{describe(conflict)}</Link> : describe(conflict)}
        {' · '}<span className="metadata">{statusLabel(conflict.status)}</span>
      </li>;
    })}
  </ul>;
}

export const approvedOnly = (conflicts) => (conflicts || []).filter(item => item.status === 'approved');
export const pendingOnly = (conflicts) => (conflicts || []).filter(item => item.status === 'submitted');
