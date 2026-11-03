import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import WithdrawRegistration from '../components/WithdrawRegistration';
import { registrationDate } from '../components/RegistrationPeriod';
import { useAuth } from '../auth/AuthContext';
import { Alert, AlertTitle, AlertDescription } from '../components/Alert';

export default function AttendeeEvents() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
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
  return <><Navbar /><main className="container">
    <div className="heading"><h1>Event registration</h1><button className="secondary" onClick={() => setRefresh(n => n + 1)}>Refresh</button></div>
    <p>All times are in Singapore time (SGT). Event information refreshes every 30 seconds.</p>
    <p><Link to="/my-registrations">View my registrations</Link></p>
    {loading && <p role="status">Loading events…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {message && <Alert><AlertTitle>Registration update</AlertTitle><AlertDescription>{message}</AlertDescription></Alert>}
    {!loading && !error && !events.length && <p>No events are available for registration.</p>}
    {events.map(event => {
      const now = Date.now();
      const canRegister = event.status === 'confirmed'
        && now >= Date.parse(event.registration_opens_at)
        && now < Date.parse(event.registration_closes_at)
        && now < Date.parse(event.start_datetime)
        && now < Date.parse(event.end_datetime);
      return <article className="panel" key={event.event_id}>
        <h2>{event.event_name}</h2><p>{event.description}</p>
        <p>Event starts: {registrationDate(event.start_datetime)}</p>
        <p>Venue: {event.venues?.length ? event.venues.join(', ') : 'Venue not assigned yet'}</p>
        <p>Registration opens: {registrationDate(event.registration_opens_at)}<br />Registration closes: {registrationDate(event.registration_closes_at)}</p>
        <p>{now < Date.parse(event.registration_opens_at) ? 'Registration is not yet open.'
          : canRegister ? 'Registration is open.' : 'Registration is unavailable for this event.'}</p>
        <p>Capacity: {event.capacity ?? 'Not set'}. Available places: {event.available_capacity ?? 'Not set'}. Waiting list: {event.waiting_list_enabled ? 'Enabled' : 'Disabled'}.</p>
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
          : selected === event.event_id ? <form onSubmit={e => register(e, event)}>
            <fieldset disabled={busy}>
              <legend>Registration details</legend>
              <label>Full name<input name="full_name" autoComplete="name" required maxLength={150} value={details.full_name} onChange={e => setDetails({ ...details, full_name: e.target.value })} /></label>
              <label>Contact email<input name="contact_email" type="text" inputMode="email" autoComplete="email" required maxLength={254} value={details.contact_email} onChange={e => setDetails({ ...details, contact_email: e.target.value })} /></label>
              <label>Contact phone<input name="contact_phone" type="tel" autoComplete="tel" required maxLength={30} value={details.contact_phone} onChange={e => setDetails({ ...details, contact_phone: e.target.value })} /></label>
              {event.waiting_list_enabled && <p>If the event is full, you will join the waiting list rather than receive a confirmed place.</p>}
              <button type="submit" disabled={!canRegister}>{busy ? 'Submitting…' : 'Submit registration'}</button>
              <button type="button" className="secondary" onClick={() => setSelected(null)}>Cancel</button>
            </fieldset>
          </form> : <button disabled={busy || !canRegister} onClick={() => { setSelected(event.event_id); setError(''); setMessage(''); }}>Register{event.waiting_list_enabled ? ' or join waiting list' : ''}</button>}
      </article>;
    })}
  </main></>;
}
