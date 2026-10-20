import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import luxonPlugin from '@fullcalendar/luxon3';
import interactionPlugin from '@fullcalendar/interaction';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { VENUE_DAYS, VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';
import { period } from '../services/venueBookings';

const LABELS = new Map([...VENUE_FACILITIES, ...VENUE_ROOM_LAYOUTS]);

function labels(values) {
  return values?.length ? values.map(value => LABELS.get(value) || value.replaceAll('_', ' ')).join(', ') : 'None specified';
}

function address(venue) {
  return [venue.unit_number, venue.building_name, `${venue.block_number} ${venue.street_name}`, venue.postal_code].filter(Boolean).join(', ');
}

function hours(operatingHours) {
  return VENUE_DAYS.map(([key, label]) => {
    const schedule = operatingHours?.[key];
    return `${label}: ${schedule?.closed ? 'Closed' : schedule?.open && schedule?.close ? `${schedule.open}–${schedule.close}` : 'Not specified'}`;
  }).join('\n');
}

// Calendar statuses and their colours. Unavailable time (outside operating
// hours) is FullCalendar's shaded non-business time; anything unmarked is available.
const SETUP_COLOR = '#a5b4fc';
const STATUSES = {
  approved: ['Confirmed', '#0f766e'],
  held: ['Tentatively held', '#d97706'],
  blocked: ['Blocked', '#64748b'],
};

function AvailabilityCalendar({ venue }) {
  const { api, can } = useAuth();
  const [selected, setSelected] = useState(null);
  const calendar = useRef(null);
  const [error, setError] = useState('');
  const staff = can('venue.unblock');

  // Venue Staff reopen an unavailable period; bookings it cancelled stay cancelled.
  async function removeBlock() {
    if (!window.confirm('Remove this unavailable period? The venue can be requested for this time again.')) return;
    try {
      await api(`/api/venues/${venue.venue_id}/unavailability/${selected.block_id}`, { method: 'DELETE' });
      setSelected(null);
      calendar.current.getApi().refetchEvents();
    } catch (err) {
      setError(err.message || 'Unable to remove the unavailable period.');
    }
  }

  // Fetches only the range on screen, each time the view or date changes.
  const load = useCallback((range, success, failure) => {
    const query = new URLSearchParams({ start: range.startStr, end: range.endStr });
    api(`/api/venues/${venue.venue_id}/availability?${query}`, { cache: 'no-store' })
      .then(data => {
        setError('');
        success([
          ...data.bookings.filter(item => item.status !== 'submitted')
            .map(item => ({ ...item, title: item.visible ? item.event_name : 'Another event' })),
          ...data.blocks.map(item => ({ ...item, status: 'blocked', title: item.reason || 'Blocked' })),
        ].map(item => ({ title: item.title, start: item.starts_at, end: item.ends_at, color: STATUSES[item.status][1], extendedProps: item }))
          // Setup before and turnaround after each booking, when the venue needs them.
          .concat(data.bookings.filter(item => item.status !== 'submitted').flatMap(item => [[item.occupied_from, item.starts_at], [item.ends_at, item.occupied_until]])
            .filter(([start, end]) => start && end && start !== end)
            .map(([start, end]) => ({ start, end, display: 'background', color: SETUP_COLOR }))));
      })
      .catch(err => { setError(err.message); failure(err); });
  }, [api, venue.venue_id]);

  const businessHours = VENUE_DAYS.flatMap(([day], index) => {
    const hours = venue.operating_hours?.[day];
    return hours?.open && hours?.close && !hours.closed ? [{ daysOfWeek: [(index + 1) % 7], startTime: hours.open, endTime: hours.close }] : [];
  });
  const link = selected?.status !== 'blocked' && selected
    && (staff ? `/review-venue-bookings/${selected.booking_id}` : selected.visible && `/venue-bookings/${selected.booking_id}`);

  return <section className="panel" style={{ '--fc-today-bg-color': '#e0f2fe' }}>
    <h2>Availability</h2>
    <p className="metadata">
      {[...Object.values(STATUSES), ['Setup / turnaround', SETUP_COLOR], ['Unavailable (closed)', '#e2e8f0']].map(([label, color]) => <span key={label} style={{ marginRight: 16 }}>
        <span style={{ display: 'inline-block', width: 12, height: 12, marginRight: 6, background: color }} />{label}
      </span>)}
      Unmarked times are available. All times are Singapore time (SGT).
    </p>
    {error && <p className="error" role="alert">{error}</p>}
    <FullCalendar
      ref={calendar}
      plugins={[dayGridPlugin, timeGridPlugin, luxonPlugin, interactionPlugin]}
      timeZone="Asia/Singapore"
      initialView="dayGridMonth"
      dateClick={({ dateStr, view }) => view.type === 'dayGridMonth' && view.calendar.changeView('timeGridDay', dateStr)}
      headerToolbar={{ left: 'prev,next today', center: 'title', right: 'timeGridDay,timeGridWeek,dayGridMonth' }}
      buttonText={{ today: 'Today', day: 'Day', week: 'Week', month: 'Month' }}
      events={load}
      businessHours={businessHours}
      eventClick={({ event }) => setSelected(event.extendedProps)}
      height="auto"
    />
    {selected && <div className="panel" role="dialog" aria-label="Slot details">
      <h3>{STATUSES[selected.status][0]}</h3>
      <p>{period(selected.starts_at, selected.ends_at)}</p>
      <p>{selected.status === 'blocked' ? selected.reason || 'No reason given'
        : selected.visible ? `${selected.event_name} (#${selected.event_id})` : 'Another event'}</p>
      {link && <Link to={link}>View booking request</Link>}{' '}
      {staff && selected.status === 'blocked' && <button type="button" className="danger-button" onClick={removeBlock}>Remove unavailable period</button>}{' '}
      <button type="button" className="secondary" onClick={() => setSelected(null)}>Close</button>
    </div>}
  </section>;
}

// Venue Staff only. Blocking a period cancels the pending and approved bookings in
// it; the database notifies their coordinators and returns them for display.
function MarkUnavailable({ venueId, onMarked }) {
  const { api } = useAuth();
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (!window.confirm('Mark this venue unavailable? Pending and approved bookings in this period will be cancelled and their Event Coordinators notified.')) return;
    setError('');
    setResult(null);
    try {
      const sgt = (name) => new Date(`${data.get(name)}:00+08:00`).toISOString();
      setResult(await api(`/api/venues/${venueId}/unavailability`, {
        method: 'POST', body: { starts_at: sgt('starts_at'), ends_at: sgt('ends_at'), reason: data.get('reason') },
      }));
      form.reset();
      onMarked();
    } catch (err) {
      setError(err.message || 'Unable to mark the venue unavailable.');
    }
  }

  return <section className="panel">
    <h2>Mark temporarily unavailable</h2>
    <p className="metadata">Pending and approved bookings during this period are cancelled and their Event Coordinators notified. Times are Singapore time (SGT).</p>
    {error && <p className="error" role="alert">{error}</p>}
    {result && <div className="venue-success" role="status">
      <p>Venue marked unavailable. {result.affected.length ? 'These bookings were cancelled and their coordinators notified:' : 'No bookings were affected.'}</p>
      {result.affected.length > 0 && <ul>{result.affected.map(item => <li key={item.booking_id}>
        <Link to={`/review-venue-bookings/${item.booking_id}`}>{item.event_name} (#{item.event_id})</Link> · {period(item.starts_at, item.ends_at)}
      </li>)}</ul>}
    </div>}
    <form className="venue-form-grid" onSubmit={submit}>
      <label>Start<input type="datetime-local" name="starts_at" required /></label>
      <label>End<input type="datetime-local" name="ends_at" required /></label>
      <label>Reason<input name="reason" required maxLength={500} /></label>
      <button type="submit">Mark unavailable</button>
    </form>
  </section>;
}

export default function VenueDetails() {
  const { venueId } = useParams();
  const { api, can } = useAuth();
  const location = useLocation();
  const [state, setState] = useState({ loading: true, venue: null, error: '' });
  const [calendarVersion, setCalendarVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, venue: null, error: '' });
    api(`/api/venues/${encodeURIComponent(venueId)}`, { cache: 'no-store', signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setState({ loading: false, venue: result.venue, error: '' }); })
      .catch(error => { if (!controller.signal.aborted) setState({ loading: false, venue: null, error: error.message || 'Unable to load venue.' }); });
    return () => controller.abort();
  }, [api, venueId]);

  const venue = state.venue;
  const details = venue ? [
    ['Capacity', `${venue.capacity.toLocaleString()} people`],
    ['Address', address(venue)],
    ['Wheelchair accessible', venue.wheelchair_accessible ? 'Yes' : 'No'],
    ['Blind accessible', venue.blind_accessible ? 'Yes' : 'No'],
    ['Accessibility notes', venue.accessibility_notes || 'None specified'],
    ['Facilities', labels(venue.facilities)],
    ['Supported room layouts', labels(venue.supported_room_layouts)],
    ['Operating hours', hours(venue.operating_hours)],
    ['Default setup time', `${venue.default_setup_minutes} minutes`],
    ['Default turnaround time', `${venue.default_turnaround_minutes} minutes`],
  ] : [];

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/venues">← All venues</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE MANAGEMENT</p>
            <h1>{venue?.venue_name || 'Venue information'}</h1>
          </div>
          {(can('venue.edit') || can('venue.delete')) && <div className="venue-page-actions">
            {can('venue.edit') && <Link className="button-link" to={`/venues/${venueId}/edit`}>Update information</Link>}
            {can('venue.delete') && <Link className="button-link danger-link" to={`/venues/${venueId}/delete`}>Delete venue</Link>}
          </div>}
        </div>
        {location.state?.message && <p className="panel venue-success" role="status">{location.state.message}</p>}
        {state.loading && <p role="status">Loading venue information…</p>}
        {state.error && <p className="panel error" role="alert">{state.error}</p>}
        {venue && <article className="panel">
          <h2>Venue characteristics</h2>
          <dl>
            {details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        </article>}
        {/* Only Event Coordinators and Venue Staff; the API refuses anyone else too. */}
        {venue && can('venue.viewCalendar') && <AvailabilityCalendar key={calendarVersion} venue={venue} />}
        {venue && can('venue.block') && <MarkUnavailable venueId={venue.venue_id} onMarked={() => setCalendarVersion(value => value + 1)} />}
      </main>
    </>
  );
}
