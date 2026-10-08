// Which event the coordinator is searching a venue for.
//
// Arriving from an event in planning, that event is the search context and its
// requirements are the filters. Arriving from the home page there is no context
// until one is chosen here, so the same page serves both routes into it.

const dateTime = (value) => value
  ? new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(value))
  : 'Not specified';

export default function EventVenueContext({
  events, eventId, event, requirements, planningNote, filtersMatchEvent,
  onSelectEvent, onApplyRequirements,
}) {
  // Only an event still being planned can receive a venue booking, so those are
  // the ones offered. An event reached directly by URL is kept in the list even
  // when it is past planning, so the page can say so rather than silently
  // forgetting which event was asked for.
  const choices = events.filter(item => item.status === 'planning' || String(item.event_id) === String(eventId));

  if (!eventId) {
    return (
      <section className="panel event-venue-context" aria-labelledby="event-context-heading">
        <h2 id="event-context-heading">Searching for a specific event?</h2>
        <p>
          Every venue in the catalogue is listed below. Choose the event you are planning to
          apply its requirements as filters and to request a booking.
        </p>
        <label>
          Event being planned
          <select value="" onChange={(change) => onSelectEvent(change.target.value)}>
            <option value="">No event — browse all venues</option>
            {choices.map(item => (
              <option key={item.event_id} value={item.event_id}>
                {item.event_name || 'Unnamed event'} (#{item.event_id})
              </option>
            ))}
          </select>
        </label>
        {choices.length === 0 && (
          <p className="metadata">
            You have no events in planning. A venue is requested for an event once its request
            has been approved.
          </p>
        )}
      </section>
    );
  }

  return (
    <section className="panel event-venue-context" aria-labelledby="event-context-heading">
      <div className="heading venue-section-heading">
        <h2 id="event-context-heading">Finding a venue for this event</h2>
        <button type="button" className="secondary" onClick={() => onSelectEvent('')}>
          Remove event filter
        </button>
      </div>

      <p className="event-venue-chip">
        <strong>{event?.event_name || `Event ${eventId}`}</strong>
        <span className="metadata"> (#{eventId})</span>
      </p>
      {event && (
        <p className="metadata">
          {dateTime(event.start_datetime)} to {dateTime(event.end_datetime)} (SGT)
        </p>
      )}

      {planningNote && <p className="panel error" role="status">{planningNote}</p>}

      {requirements.length > 0 && (
        <>
          <p>This event needs a venue that provides:</p>
          <dl className="event-venue-requirements">
            {requirements.map(requirement => (
              <div key={requirement.field}>
                <dt>{requirement.label}</dt>
                <dd>{requirement.value}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
      {requirements.length === 0 && (
        <p className="metadata">This event records no venue requirements, so every venue can be requested for it.</p>
      )}

      {/* Clearing the filters is allowed and shows the whole catalogue. The
          requirements still decide what may be requested, so this only offers
          the filters back rather than reinstating them. */}
      {!filtersMatchEvent && (
        <p>
          <button type="button" className="secondary" onClick={onApplyRequirements}>
            Filter by this event’s requirements
          </button>
        </p>
      )}
      {!filtersMatchEvent && (
        <p className="metadata">
          Venues that cannot meet the requirements above are shown but cannot be requested
          for this event.
        </p>
      )}
    </section>
  );
}
