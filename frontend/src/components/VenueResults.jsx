// The venues a search returned, and what may be done with each one.
//
// Shared by the venue search catalogue and the name-search results so both
// surfaces offer, and refuse, a booking request on the same terms.

import { Link } from 'react-router-dom';
import BookingConflicts from './BookingConflicts';

const readable = (value) => value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());

function address(venue) {
  return [
    venue.unit_number,
    venue.building_name,
    [venue.block_number, venue.street_name].filter(Boolean).join(' '),
    venue.postal_code,
  ].filter(Boolean).join(', ');
}

function VenueResult({ venue, eventId, canRequest }) {
  const characteristics = [...(venue.facilities || []), ...(venue.supported_room_layouts || [])];
  // Absent without an event: no event, no requirements, nothing to fail.
  const unmet = venue.unmet_requirements || [];
  const conflicts = venue.conflicts || [];
  const eligible = venue.eligible !== false;
  const unmetId = `unmet-${venue.venue_id}`;

  return (
    <article className={`panel venue-card venue-result${eligible ? '' : ' venue-result-ineligible'}`}>
      <h3>{venue.venue_name}</h3>
      <p>{address(venue) || 'Address not specified'}</p>
      <p className="metadata">
        Capacity: {Number.isFinite(venue.capacity) ? venue.capacity.toLocaleString() : 'Not specified'}
      </p>
      <div className="venue-card-tags" aria-label="Venue characteristics">
        {venue.wheelchair_accessible && <span>Wheelchair accessible</span>}
        {venue.blind_accessible && <span>Blind accessible</span>}
        {characteristics.slice(0, 4).map(value => <span key={value}>{readable(value)}</span>)}
        {characteristics.length > 4 && <span>+{characteristics.length - 4} more</span>}
      </div>

      {/* A venue can fail on either count, and both reasons are shown: a
          booked venue that also lacks a facility should say so, or the
          coordinator would wait for it to come free for nothing. */}
      {!eligible && (
        <div className="venue-unmet" id={unmetId}>
          {unmet.length > 0 && <>
            <p><strong>Does not meet this event’s requirements:</strong></p>
            <ul>
              {unmet.map(requirement => (
                <li key={requirement.field}>{requirement.label}: {requirement.detail}</li>
              ))}
            </ul>
          </>}
          {conflicts.length > 0 && <>
            <p><strong>Already booked during this event’s time:</strong></p>
            <BookingConflicts conflicts={conflicts} />
          </>}
        </div>
      )}

      <div className="venue-result-actions">
        <Link to={`/venues/${venue.venue_id}`}>View venue information</Link>
        {eventId && eligible && canRequest && (
          <Link
            className="button-link"
            to={`/venue-bookings?event_id=${encodeURIComponent(eventId)}&venue_id=${encodeURIComponent(venue.venue_id)}`}
          >
            Request this venue
          </Link>
        )}
        {eventId && eligible && !canRequest && (
          <span className="metadata">A booking can only be requested while the event is in planning.</span>
        )}
        {/* Disabled rather than hidden: the coordinator asked to see this venue,
            so the page says why it cannot be used instead of losing it. */}
        {eventId && !eligible && (
          <button type="button" disabled aria-describedby={unmetId}>
            {unmet.length === 0 && conflicts.length > 0
              ? 'Booked during this event’s time'
              : 'Cannot be requested for this event'}
          </button>
        )}
      </div>
    </article>
  );
}

export default function VenueResults({
  venues, eventId, canRequest = true, loading, error, emptyMessage, eligibleCount,
}) {
  return (
    <section aria-labelledby="venue-results-heading">
      <div className="heading venue-section-heading">
        <h2 id="venue-results-heading">Venues</h2>
        {!loading && !error && (
          <span className="metadata">
            {venues.length} {venues.length === 1 ? 'venue' : 'venues'}
            {eventId && Number.isInteger(eligibleCount) && `, ${eligibleCount} can be requested`}
          </span>
        )}
      </div>
      {loading && <p role="status">Searching venues…</p>}
      {error && <p className="panel error" role="alert">{error}</p>}
      {!loading && !error && venues.length === 0 && (
        <p className="panel">{emptyMessage || 'No venues match the current filters.'}</p>
      )}
      {!loading && venues.length > 0 && (
        <div className="venue-card-grid">
          {venues.map(venue => (
            <VenueResult key={venue.venue_id} venue={venue} eventId={eventId} canRequest={canRequest} />
          ))}
        </div>
      )}
    </section>
  );
}
