import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import luxonPlugin from '@fullcalendar/luxon3';
import interactionPlugin from '@fullcalendar/interaction';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { hasAccess } from '../auth/access';
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
  submitted: ['Tentatively held', '#d97706'],
  blocked: ['Blocked', '#64748b'],
};

function AvailabilityCalendar({ venue }) {
  const { api, account } = useAuth();
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const staff = hasAccess(account.user?.roles, ['venue staff']);

  // Fetches only the range on screen, each time the view or date changes.
  const load = useCallback((range, success, failure) => {
    const query = new URLSearchParams({ start: range.startStr, end: range.endStr });
    api(`/api/venues/${venue.venue_id}/availability?${query}`, { cache: 'no-store' })
      .then(data => {
        setError('');
        success([
          ...data.bookings.map(item => ({ ...item, title: item.visible ? item.event_name : 'Another event' })),
          ...data.blocks.map(item => ({ ...item, status: 'blocked', title: item.reason || 'Blocked' })),
        ].map(item => ({ title: item.title, start: item.starts_at, end: item.ends_at, color: STATUSES[item.status][1], extendedProps: item }))
          // Setup before and turnaround after each booking, when the venue needs them.
          .concat(data.bookings.flatMap(item => [[item.occupied_from, item.starts_at], [item.ends_at, item.occupied_until]])
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
      <button type="button" className="secondary" onClick={() => setSelected(null)}>Close</button>
    </div>}
  </section>;
}

export default function VenueDetails() {
  const { venueId } = useParams();
  const { api, canAccess, account } = useAuth();
  const location = useLocation();
  const [state, setState] = useState({ loading: true, venue: null, error: '' });

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
          {canAccess(`/venues/${venueId}/edit`) && <div className="venue-page-actions">
            <Link className="button-link" to={`/venues/${venueId}/edit`}>Update information</Link>
            <Link className="button-link danger-link" to={`/venues/${venueId}/delete`}>Delete venue</Link>
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
        {venue && hasAccess(account.user?.roles, ['event coordinator', 'venue staff']) && <AvailabilityCalendar venue={venue} />}
      </main>
    </>
  );
}
