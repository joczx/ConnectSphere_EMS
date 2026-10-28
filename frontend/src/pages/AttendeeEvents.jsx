import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { registrationDate } from '../components/RegistrationPeriod';
import { useAuth } from '../auth/AuthContext';

const messages = { open: 'Registration is open.', not_open: 'Registration is not yet open.', closed: 'Registration has closed.', unavailable: 'Registration is unavailable for this event.' };
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
      const data = await api(`/api/events/${event.event_id}/registrations`, { method: 'POST', body: details });
      const emailMessage = data.notification === 'queued' ? ' A confirmation email has been queued.'
        : data.notification === 'sent' ? ' A confirmation email has already been sent.' : '';
      setMessage((data.registration.status === 'waiting_list' ? 'You have joined the waiting list. Your place is not confirmed.' : 'You are registered for the event.') + emailMessage);
      setSelected(null);
      setRefresh(n => n + 1);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function withdraw(event) {
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await api(`/api/events/${event.event_id}/registrations/withdraw`, { method: 'POST', body: {} });
      setEvents(current => current.map(item => item.event_id === event.event_id
        ? { ...item, my_registration: data.registration.status, available_capacity: data.available_capacity } : item));
      setMessage(data.message);
      setRefresh(n => n + 1);
    } catch (err) { setError(err.message || 'Unable to withdraw your registration.'); }
    finally { setBusy(false); }
  }
  return <><Navbar /><main className="container">
    <div className="heading"><h1>Event registration</h1><button className="secondary" onClick={() => setRefresh(n => n + 1)}>Refresh</button></div>
    <p>All times are in Singapore time (SGT). Event information refreshes every 30 seconds.</p>
    <p><Link to="/my-registrations">View my registrations</Link></p>
    {loading && <p role="status">Loading events…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!loading && !error && !events.length && <p>No events are available for registration.</p>}
    {events.map(event => {
      const now = Date.now();
      const status = event.status !== 'confirmed' || now >= Date.parse(event.end_datetime) ? 'unavailable'
        : now < Date.parse(event.registration_opens_at) ? 'not_open'
          : now >= Date.parse(event.registration_closes_at) ? 'closed' : 'open';
      return <article className="panel" key={event.event_id}>
        <h2>{event.event_name}</h2><p>{event.description}</p>
        <p>Event starts: {registrationDate(event.start_datetime)}</p>
        <p>Registration opens: {registrationDate(event.registration_opens_at)}<br />Registration closes: {registrationDate(event.registration_closes_at)}</p>
        <p>{messages[status]}</p>
        <p>Capacity: {event.capacity ?? 'Not set'}. Available places: {event.available_capacity ?? 'Not set'}. Waiting list: {event.waiting_list_enabled ? 'Enabled' : 'Disabled'}.</p>
        {event.my_registration === 'withdrawn' && <p>Your registration has been withdrawn.</p>}
        {['registered', 'waiting_list'].includes(event.my_registration) ? <>
          <p>{event.my_registration === 'registered' ? 'You are registered.' : 'You are on the waiting list.'}</p>
          <button type="button" className="secondary" disabled={busy || !(now < Date.parse(event.start_datetime))} onClick={() => withdraw(event)}>Withdraw registration</button>
          {!(now < Date.parse(event.start_datetime)) && <p>Registration cannot be withdrawn at or after the event start time.</p>}
        </>
          : selected === event.event_id ? <form onSubmit={e => register(e, event)}>
            <fieldset disabled={busy}>
              <legend>Registration details</legend>
              <label>Full name<input name="full_name" autoComplete="name" required maxLength={150} value={details.full_name} onChange={e => setDetails({ ...details, full_name: e.target.value })} /></label>
              <label>Contact email<input name="contact_email" type="email" autoComplete="email" required maxLength={254} value={details.contact_email} onChange={e => setDetails({ ...details, contact_email: e.target.value })} /></label>
              <label>Contact phone<input name="contact_phone" type="tel" autoComplete="tel" required maxLength={30} value={details.contact_phone} onChange={e => setDetails({ ...details, contact_phone: e.target.value })} /></label>
              {event.waiting_list_enabled && <p>If the event is full, you will join the waiting list rather than receive a confirmed place.</p>}
              <button type="submit" disabled={status !== 'open'}>{busy ? 'Submitting…' : 'Submit registration'}</button>
              <button type="button" className="secondary" onClick={() => setSelected(null)}>Cancel</button>
            </fieldset>
          </form> : <button disabled={busy || status !== 'open'} onClick={() => { setSelected(event.event_id); setError(''); setMessage(''); }}>Register{event.waiting_list_enabled ? ' or join waiting list' : ''}</button>}
      </article>;
    })}
  </main></>;
}
