import { useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import { RegistrationNavigation, EventDateTile, RegistrationBadge } from '../components/AttendeeRegistrationUI';
import WithdrawRegistration from '../components/WithdrawRegistration';
import { registrationDate } from '../components/RegistrationPeriod';
import { useAuth } from '../auth/AuthContext';
import { Alert, AlertTitle, AlertDescription } from '../components/Alert';

export default function AttendeeEvents() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState({ full_name: '', contact_email: '', contact_phone: '' });
  useEffect(() => {
    const controller = new AbortController();
    api('/api/registration-events', { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted) { setEvents(data.events || []); setError(''); } })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    const reload = () => setRefresh(n => n + 1);
    const timer = setInterval(reload, 30000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, refresh]);
  async function register(e, event) {
    e.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await api(`/api/events/${event.event_id}/registrations`, {
        method: 'POST', body: details, successFeedback: false,
      });
      setMessage(data.message || (data.registration.status === 'waiting_list'
        ? 'You have joined the waiting list. Your place is not confirmed.' : 'You are registered for the event.'));
      setSelected(null);
      setRefresh(n => n + 1);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  const visibleEvents = events.filter(event => [event.event_name, event.description, ...(event.venues || [])]
    .some(value => String(value || '').toLowerCase().includes(search.trim().toLowerCase())));
  return <><Navbar /><main className="container attendee-workspace">
    <div className="attendee-page-header"><div><p className="attendee-eyebrow">ATTENDEE PORTAL</p><h1>Event registration</h1>
      <p>Find your next event and reserve your place.</p></div><button type="button" className="secondary" onClick={() => setRefresh(n => n + 1)}>Refresh</button></div>
    <RegistrationNavigation current="events" />
    <div className="attendee-toolbar"><label className="attendee-search">Search events<input type="search" placeholder="Search by event or venue" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <span className="attendee-sync">Times in SGT &middot; Updates every 30 seconds</span></div>
    {loading && <p role="status">Loading events...</p>}
    {error && <Alert variant="destructive"><AlertTitle>Something went wrong</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {message && <Alert><AlertTitle>Registration update</AlertTitle><AlertDescription>{message}</AlertDescription></Alert>}
    {!loading && !error && !events.length && <div className="attendee-empty"><h2>No events are available for registration.</h2><p>Check back soon for upcoming events.</p></div>}
    {!loading && !error && events.length > 0 && <p className="attendee-result-count" role="status">{visibleEvents.length} {visibleEvents.length === 1 ? 'event' : 'events'} available</p>}
    {!loading && !error && events.length > 0 && !visibleEvents.length && <div className="attendee-empty"><h2>No matching events</h2><p>Try a different event name or venue.</p><button className="secondary" onClick={() => setSearch('')}>Clear search</button></div>}
    <div className="attendee-cards">{visibleEvents.map(event => {
      const now = Date.now();
      const canRegister = event.status === 'confirmed'
        && now >= Date.parse(event.registration_opens_at)
        && now < Date.parse(event.registration_closes_at)
        && now < Date.parse(event.start_datetime)
        && now < Date.parse(event.end_datetime);
      return <article className="panel attendee-card" key={event.event_id}>
        <div className="attendee-card-header"><EventDateTile value={event.start_datetime} /><div><h2>{event.event_name}</h2>
          <div className="attendee-card-badges">
            <span className={`registration-status ${canRegister ? 'registration-status-registered' : ''}`}>{canRegister ? 'Open for registration' : 'Registration unavailable'}</span>
            {event.my_registration && <RegistrationBadge status={event.my_registration} />}
          </div></div></div>
        <p className="attendee-description">{event.description}</p>
        <dl className="attendee-details">
          <div><dt>Event starts</dt><dd>{registrationDate(event.start_datetime)}</dd></div>
          <div><dt>Event ends</dt><dd>{registrationDate(event.end_datetime)}</dd></div>
          <div className="attendee-wide"><dt>Venue</dt><dd>{event.venues?.length ? event.venues.join(', ') : 'Venue not assigned yet'}</dd></div>
          <div><dt>Registration opens</dt><dd>{registrationDate(event.registration_opens_at)}</dd></div>
          <div><dt>Registration closes</dt><dd>{registrationDate(event.registration_closes_at)}</dd></div>
        </dl>
        <div className="attendee-capacity"><span><strong>{event.available_capacity ?? '?'}</strong> available places <span className="attendee-muted">/ {event.capacity ?? '?'} total</span></span><span>Waiting list: {event.waiting_list_enabled ? 'Enabled' : 'Disabled'}</span></div>
        <div className="attendee-card-actions">
        <p className="attendee-availability">{now < Date.parse(event.registration_opens_at) ? 'Registration is not yet open.'
          : canRegister ? 'Registration is open.' : 'Registration is unavailable for this event.'}</p>
        {event.my_registration === 'withdrawn' && <p>Your registration has been withdrawn.</p>}
        {['registered', 'waiting_list'].includes(event.my_registration) ? <>
          <p>{event.my_registration === 'registered' ? 'You are registered.' : 'You are on the waiting list.'}</p>
          <WithdrawRegistration eventId={event.event_id} startDatetime={event.start_datetime} status={event.my_registration} disabled={busy}
            onWithdrawn={data => {
              setEvents(current => current.map(item => item.event_id === event.event_id
                ? { ...item, my_registration: data.registration.status, available_capacity: data.available_capacity } : item));
              setError(''); setMessage(data.message);
              setRefresh(n => n + 1);
            }} />
        </>
          : selected === event.event_id ? <form className="attendee-registration-form" onSubmit={e => register(e, event)}>
            <fieldset disabled={busy}>
              <legend>Registration details</legend>
              <label>Full name<input autoFocus name="full_name" autoComplete="name" required maxLength={150} value={details.full_name} onChange={e => setDetails({ ...details, full_name: e.target.value })} /></label>
              <label>Contact email<input name="contact_email" type="text" inputMode="email" autoComplete="email" required maxLength={254} value={details.contact_email} onChange={e => setDetails({ ...details, contact_email: e.target.value })} /></label>
              <label>Contact phone<input name="contact_phone" type="tel" autoComplete="tel" required maxLength={30} value={details.contact_phone} onChange={e => setDetails({ ...details, contact_phone: e.target.value })} /></label>
              {event.waiting_list_enabled && <p>If the event is full, you will join the waiting list rather than receive a confirmed place.</p>}
              <div className="attendee-form-actions"><button type="submit" disabled={!canRegister}>{busy ? 'Submitting...' : 'Submit registration'}</button>
              <button type="button" className="secondary" onClick={() => setSelected(null)}>Cancel</button></div>
            </fieldset>
          </form> : <button disabled={busy || !canRegister} onClick={() => { setSelected(event.event_id); setError(''); setMessage(''); }}>Register{event.waiting_list_enabled ? ' or join waiting list' : ''}</button>}
        </div>
      </article>;
    })}</div>
  </main></>;
}
