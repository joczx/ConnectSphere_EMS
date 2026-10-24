import { useEffect, useState } from 'react';
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
  async function register(event) {
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await api(`/api/events/${event.event_id}/registrations`, { method: 'POST', body: {} });
      setMessage(data.registration.status === 'waiting_list' ? 'You have joined the waiting list.' : 'You are registered for the event.');
      setRefresh(n => n + 1);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <><Navbar /><main className="container">
    <div className="heading"><h1>Event registration</h1><button className="secondary" onClick={() => setRefresh(n => n + 1)}>Refresh</button></div>
    <p>All times are in Singapore time (SGT). Event information refreshes every 30 seconds.</p>
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
        <p>Capacity: {event.capacity ?? 'Not set'}. Waiting list: {event.waiting_list_enabled ? 'Enabled' : 'Disabled'}.</p>
        {event.my_registration ? <p>{event.my_registration === 'registered' ? 'You are registered.' : 'You are on the waiting list.'}</p>
          : <button disabled={busy || status !== 'open'} onClick={() => register(event)}>Register{event.waiting_list_enabled ? ' or join waiting list' : ''}</button>}
      </article>;
    })}
  </main></>;
}
