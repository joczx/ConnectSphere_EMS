import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { registrationDate } from '../components/RegistrationPeriod';
import { useAuth } from '../auth/AuthContext';

const statusLabels = { registered: 'Confirmed', waiting_list: 'Waitlisted', withdrawn: 'Withdrawn' };

export default function MyRegistrations({ embedded = false }) {
  const Heading = embedded ? 'h2' : 'h1';
  const Container = embedded ? 'section' : 'main';
  const EventHeading = embedded ? 'h3' : 'h2';
  const { api } = useAuth();
  const [registrations, setRegistrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api('/api/my-registrations', { signal: controller.signal, cache: 'no-store' })
      .then(data => {
        if (!controller.signal.aborted) { setRegistrations(data.registrations || []); setError(''); }
      })
      .catch(err => { if (!controller.signal.aborted) setError(err.message || 'Unable to load your registrations.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 30000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, refresh]);

  return <>{!embedded && <Navbar />}<Container className={embedded ? "dashboard-overview" : "container"} aria-label="My registrations">
    <div className="heading"><Heading>My registrations</Heading>
      <button type="button" className="secondary" onClick={() => setRefresh(value => value + 1)}>Refresh</button>
    </div>
    <p>Your event registrations, including past events and withdrawals. All times are in Singapore time (SGT). Statuses refresh every 30 seconds.</p>
    <p><Link to="/event-registration">Browse events or manage your registration</Link></p>
    {embedded && !loading && !error && <div className="dashboard-metrics">
      {Object.entries(statusLabels).map(([status, label]) => <article className="panel dashboard-metric" key={status}>
        <h3>{label}</h3><strong>{registrations.filter(item => item.status === status).length}</strong>
      </article>)}
    </div>}
    {loading && <p role="status">Loading your registrations…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {!loading && !error && !registrations.length && <p role="status">You have no registration records.</p>}
    {!error && registrations.map(item => <article className="panel" key={item.event_id}>
      <EventHeading>{item.event_name}</EventHeading>
      <p><strong>Registration status: {statusLabels[item.status] || 'Unknown'}</strong></p>
      {item.status === 'waiting_list' && <p>You are on the waiting list. Your place is not confirmed.</p>}
      {item.event_status === 'cancelled' && <p>This event has been cancelled.</p>}
      {item.event_status === 'completed' && <p>This event has ended.</p>}
      <dl className="detail-grid">
        <div><dt>Starts</dt><dd>{registrationDate(item.start_datetime)}</dd></div>
        <div><dt>Ends</dt><dd>{registrationDate(item.end_datetime)}</dd></div>
        <div><dt>Venue</dt><dd>{item.venues?.length ? item.venues.join(', ') : 'Venue not assigned yet'}</dd></div>
      </dl>
    </article>)}
  </Container></>;
}
