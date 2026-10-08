import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { Alert, AlertTitle, AlertDescription } from '../components/Alert';
import BookingConflicts from '../components/BookingConflicts';
import { useAuth } from '../auth/AuthContext';
import { byStatus, period, venueBookingsApi } from '../services/venueBookings';

const formatTime = (value) => value
  ? new Date(value).toLocaleString('en-SG', { timeZone: 'Asia/Singapore' })
  : 'Not specified';

// The event's requirements, as the text a Venue Staff reviewer will read. The
// server supplies the wording so the request says the same thing the search
// page and the eligibility check said.
const requirementsText = (requirements) => requirements.length
  ? requirements.map(item => `${item.label}: ${item.value}`).join('\n')
  : 'None';

export default function VenueBookings() {
  const { api } = useAuth();
  const [params] = useSearchParams();
  const eventId = params.get('event_id') || '';
  const venueId = params.get('venue_id') || '';
  // A request is always made for one event and one venue, both chosen in Venue
  // Search. Without them there is nothing to request here, only requests to
  // read, so the form is not offered.
  const requesting = !!(eventId && venueId);

  const [data, setData] = useState(null);
  const [choice, setChoice] = useState(null);
  const [requirements, setRequirements] = useState('');
  const [attendance, setAttendance] = useState('');
  const [error, setError] = useState('');
  const [unmet, setUnmet] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [alerts, setAlerts] = useState([]);

  // Decisions Venue Staff have made since the coordinator last looked. Not
  // loading them must not stop the requests themselves from showing, and the
  // outcome is on each request anyway, so a failure here stays quiet.
  useEffect(() => {
    const controller = new AbortController();
    venueBookingsApi(api, '/alerts', { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setAlerts(result.alerts || []); })
      .catch(() => { if (!controller.signal.aborted) setAlerts([]); });
    return () => controller.abort();
  }, [api, version]);

  async function dismissAlerts() {
    const ids = alerts.map(alert => alert.notification_id);
    setAlerts([]);
    try {
      await venueBookingsApi(api, '/alerts/dismiss', { method: 'POST', body: { notification_ids: ids } });
    } catch {
      // Shown again on the next load, which is the honest outcome of a dismissal
      // that did not save.
      setVersion(value => value + 1);
    }
  }
  const submitting = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setData(null);
    api('/api/venue-bookings', { cache: 'no-store', signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [api, version]);

  // The event and the venue being requested, with the event's requirements and
  // the verdict for this venue already decided by the server.
  useEffect(() => {
    if (!requesting) {
      setChoice(null);
      return undefined;
    }
    const controller = new AbortController();
    setChoice(null);
    (async () => {
      const [criteria, venue] = await Promise.all([
        api(`/api/events/${encodeURIComponent(eventId)}/venue-criteria`, {
          cache: 'no-store', signal: controller.signal,
        }),
        api(`/api/venues/${encodeURIComponent(venueId)}?event_id=${encodeURIComponent(eventId)}`, {
          cache: 'no-store', signal: controller.signal,
        }),
      ]);
      if (controller.signal.aborted) return;
      setChoice({ ...criteria, venue: venue.venue });
      setRequirements(requirementsText(criteria.requirements || []));
      setAttendance(criteria.event?.capacity_needed ?? '');
    })().catch(err => {
      if (!controller.signal.aborted) setError(err.message || 'Unable to load this request.');
    });
    return () => controller.abort();
  }, [api, eventId, venueId, requesting]);

  const event = choice?.event;
  const venue = choice?.venue;
  const eligible = venue ? venue.eligible !== false : false;
  const planning = choice ? choice.planning !== false : false;

  async function submit(submitEvent) {
    submitEvent.preventDefault();
    if (submitting.current || !event || !venue) return;
    setError('');
    setUnmet([]);
    setConflicts([]);
    submitting.current = true;
    setBusy(true);
    try {
      const result = await api('/api/venue-bookings', {
        method: 'POST',
        body: {
          event_id: Number(eventId),
          venue_id: venue.venue_id,
          event_name: event.event_name,
          // Copied from the event rather than entered again: the database
          // refuses a request whose period disagrees with the event it names.
          starts_at: event.start_datetime,
          ends_at: event.end_datetime,
          attendance: Number(attendance),
          venue_requirements: requirements,
        },
      });
      setConfirmation({ ...result.booking, venue_name: venue.venue_name });
      setVersion(value => value + 1);
    } catch (err) {
      setUnmet(err.data?.unmet_requirements || []);
      setConflicts(err.data?.conflicts || []);
      setError([err.message, ...Object.values(err.details || {})].join(' '));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return <><Navbar /><main className="container">
    {eventId
      ? <Link to={`/events/${encodeURIComponent(eventId)}`}>← Back to event planning</Link>
      : <Link to="/home">← Home</Link>}
    <div className="heading">
      <div>
        <p className="eyebrow">VENUE BOOKINGS</p>
        <h1>Venue booking requests</h1>
      </div>
      <button type="button" className="secondary" disabled={busy} onClick={() => setVersion(value => value + 1)}>
        Refresh requests
      </button>
    </div>

    {!data && !error && <p role="status">Loading booking requests…</p>}

    {confirmation && <section className="panel" role="status">
      <h2>Booking request submitted</h2>
      <p>Venue Staff can now review your request for {confirmation.venue_name}. It is awaiting review.</p>
      <p>Reference: {confirmation.booking_id}</p>
      {eventId && <Link className="button-link" to={`/events/${encodeURIComponent(eventId)}`}>
        Back to event planning
      </Link>}
    </section>}

    {/* Nothing to request without an event and a venue, so this says where the
        request starts instead of offering a form that cannot be filled in. */}
    {!requesting && data?.can_submit && <section className="panel">
      <h2>Requesting a venue</h2>
      <p>
        A venue is requested for one event. Open the event you are planning, choose
        <strong> Find venues for this event</strong>, then request a venue that meets its
        requirements.
      </p>
      <Link className="button-link" to="/events">Go to my events</Link>
    </section>}

    {requesting && !choice && !error && <p role="status">Loading the event and venue…</p>}

    {requesting && choice && !confirmation && <form className="panel" onSubmit={submit}>
      <h2>Request {venue?.venue_name}</h2>
      <p>
        For <strong>{event?.event_name}</strong> (#{event?.event_id}). The period and expected
        attendance come from the event, in Singapore time (UTC+8).
      </p>

      {choice.planning_note && <Alert variant="destructive" className="page-alert">
        <AlertTitle>This event is no longer in planning</AlertTitle>
        <AlertDescription>{choice.planning_note}</AlertDescription>
      </Alert>}

      {!eligible && (venue.unmet_requirements || []).length > 0 && <Alert variant="destructive" className="page-alert">
        <AlertTitle>This venue does not meet the event’s requirements</AlertTitle>
        <AlertDescription>
          <ul>{venue.unmet_requirements.map(item => (
            <li key={item.field}>{item.label}: {item.detail}</li>
          ))}</ul>
          <p>Choose another venue, or change the event if its requirements have moved on.</p>
        </AlertDescription>
      </Alert>}

      {(venue?.conflicts || []).length > 0 && <Alert variant="destructive" className="page-alert">
        <AlertTitle>This venue is already booked during this event’s time</AlertTitle>
        <AlertDescription>
          <BookingConflicts conflicts={venue.conflicts} />
          <p>An approved booking makes the venue unavailable for its period. Choose another venue.</p>
        </AlertDescription>
      </Alert>}

      <dl>
        <div><dt>Venue</dt><dd>{venue?.venue_name}</dd></div>
        <div><dt>Start</dt><dd>{formatTime(event?.start_datetime)}</dd></div>
        <div><dt>End</dt><dd>{formatTime(event?.end_datetime)}</dd></div>
      </dl>

      <fieldset disabled={busy || !eligible || !planning}>
        <label>
          Expected attendance
          {/* Fixed by the event whenever the event records it, so a request can
              never ask for a headcount the event does not have. */}
          <input
            type="number"
            min="1"
            max="2147483647"
            step="1"
            required
            readOnly={event?.capacity_needed != null}
            value={attendance}
            onChange={(change) => setAttendance(change.target.value)}
          />
        </label>
        <label>
          Venue requirements
          <textarea
            required
            maxLength={5000}
            rows={6}
            value={requirements}
            onChange={(change) => setRequirements(change.target.value)}
          />
        </label>
        <p className="metadata">
          Prefilled from the event. Add anything else Venue Staff need to know about the setup.
        </p>
        <button type="submit">{busy ? 'Submitting…' : 'Submit booking request'}</button>
      </fieldset>
      <p>
        <Link to={`/venue-search?event_id=${encodeURIComponent(eventId)}`}>
          Choose a different venue
        </Link>
      </p>
    </form>}

    {error && <Alert variant="destructive" className="page-alert">
      <AlertTitle>Unable to complete request</AlertTitle>
      <AlertDescription>
        {error}
        {unmet.length > 0 && <ul>{unmet.map(item => <li key={item}>{item}</li>)}</ul>}
        {/* Booked between loading this page and submitting it. */}
        <BookingConflicts conflicts={conflicts} />
      </AlertDescription>
    </Alert>}

    {/* Venue Staff read every request through the same endpoint, but deciding
        them happens on the review page, so they are sent there. */}
    {data?.can_review && <section className="panel">
      <h2>Reviewing requests</h2>
      <p>Requests from Event Coordinators are reviewed on the Review Venue Bookings page.</p>
      <Link className="button-link" to="/review-venue-bookings">Go to Review Venue Bookings</Link>
    </section>}

    {data && !data.can_review && <>
      {alerts.length > 0 && <section className="panel booking-alerts" role="status" aria-labelledby="booking-alerts-heading">
        <div className="heading venue-section-heading">
          <h2 id="booking-alerts-heading">New decisions on your requests</h2>
          <button type="button" className="secondary" onClick={dismissAlerts}>Dismiss</button>
        </div>
        <ul>{alerts.map(alert => <li key={alert.notification_id}>
          {alert.message} <span className="metadata">({formatTime(alert.created_at)})</span>{' '}
          <Link to={'/venue-bookings/' + alert.venue_booking_id}>View request</Link>
        </li>)}</ul>
      </section>}

      <p>Dates and times below are in Singapore time (UTC+8).</p>
      {!data.bookings.length && <p className="panel">You have not requested a venue yet.</p>}
      {/* Modelled on My Event Requests: one section per stage, so what is still
          waiting is never mixed in with what has been decided. */}
      {[['Submitted', 'submitted'], ['Approved', 'approved'], ['Rejected', 'rejected']].map(([title, status]) => {
        const items = byStatus(data.bookings, status);
        return items.length > 0 && <section key={status}>
          <h2>{title} <span className="metadata">({items.length})</span></h2>
          <div className="event-list">{items.map(booking => <BookingCard key={booking.booking_id} booking={booking} />)}</div>
        </section>;
      })}
    </>}
  </main></>;
}

// Just enough to tell requests apart; everything else is one click away on the
// request's own page, as on My Event Requests.
function BookingCard({ booking }) {
  return <Link className="panel event-link" to={'/venue-bookings/' + booking.booking_id}>
    <h2>{booking.event_name}</h2>
    {booking.event_id && <p className="metadata">Event #{booking.event_id}</p>}
    <p>{booking.venue_name}</p>
    <p className="metadata">{period(booking.starts_at, booking.ends_at)}</p>
    <span>View request →</span>
  </Link>;
}
