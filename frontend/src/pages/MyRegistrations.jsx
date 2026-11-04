import { useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import { RegistrationNavigation, EventDateTile, RegistrationBadge, registrationLabels as statusLabels } from '../components/AttendeeRegistrationUI';
import { Alert, AlertTitle, AlertDescription } from '../components/Alert';
import WithdrawRegistration from '../components/WithdrawRegistration';
import { registrationDate } from '../components/RegistrationPeriod';
import { useAuth } from '../auth/AuthContext';



export default function MyRegistrations({ embedded = false }) {
  const Heading = embedded ? 'h2' : 'h1';
  const Container = embedded ? 'section' : 'main';
  const EventHeading = embedded ? 'h3' : 'h2';
  const { api } = useAuth();
  const [registrations, setRegistrations] = useState([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [message, setMessage] = useState('');
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

  const visibleRegistrations = registrations.filter(item => (filter === 'all' || item.status === filter)
    && [item.event_name, ...(item.venues || [])].some(value => String(value || '').toLowerCase().includes(search.trim().toLowerCase())));
  return <>{!embedded && <Navbar />}<Container className={embedded ? "dashboard-overview attendee-workspace" : "container attendee-workspace"} aria-label="My registrations">
    <div className="attendee-page-header"><div>{!embedded && <p className="attendee-eyebrow">ATTENDEE PORTAL</p>}<Heading>My registrations</Heading>
      <p>Your places, waiting lists and registration history in one place.</p></div>
      <button type="button" className="secondary" onClick={() => setRefresh(value => value + 1)}>Refresh</button>
    </div>
    <RegistrationNavigation current="registrations" />
    {!loading && !error && <div className="attendee-summary">
      {Object.entries(statusLabels).map(([status, label]) => <div key={status}>
        <span className={`attendee-summary-dot registration-status-${status}`} /><span>{label}</span><strong>{registrations.filter(item => item.status === status).length}</strong>
      </div>)}
    </div>}
    <div className="attendee-toolbar"><label className="attendee-search">Search registrations<input type="search" placeholder="Search by event or venue" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <span className="attendee-sync">Times in SGT &middot; Updates every 30 seconds</span></div>
    <div className="attendee-filters" role="group" aria-label="Filter registrations">
      {Object.entries({ all: 'All registrations', ...statusLabels }).map(([status, label]) => <button key={status} type="button" aria-pressed={filter === status} onClick={() => setFilter(status)}>{label}<span>{status === 'all' ? registrations.length : registrations.filter(item => item.status === status).length}</span></button>)}
    </div>
    {loading && <p role="status">Loading your registrations...</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {message && <Alert><AlertTitle>Registration update</AlertTitle><AlertDescription>{message}</AlertDescription></Alert>}
    {!loading && !error && !registrations.length && <div className="attendee-empty" role="status"><EventHeading>You have no registration records.</EventHeading><p>Browse upcoming events to find something you would like to join.</p></div>}
    {!loading && !error && registrations.length > 0 && !visibleRegistrations.length && <div className="attendee-empty" role="status"><EventHeading>No matching registrations</EventHeading><p>Try a different search or status filter.</p><button className="secondary" onClick={() => { setSearch(''); setFilter('all'); }}>Clear filters</button></div>}
    <div className="attendee-cards">{!error && visibleRegistrations.map(item => <article className="panel attendee-card" key={item.event_id}>
      <div className="attendee-card-header"><EventDateTile value={item.start_datetime} /><div><EventHeading>{item.event_name}</EventHeading><RegistrationBadge status={item.status} /></div></div>
      {item.status === 'waiting_list' && <p>You are on the waiting list. Your place is not confirmed.</p>}
      {item.event_status === 'cancelled' && <p>This event has been cancelled.</p>}
      {item.event_status === 'completed' && <p>This event has ended.</p>}
      <dl className="attendee-details">
        <div><dt>Starts</dt><dd>{registrationDate(item.start_datetime)}</dd></div>
        <div><dt>Ends</dt><dd>{registrationDate(item.end_datetime)}</dd></div>
        <div className="attendee-wide"><dt>Venue</dt><dd>{item.venues?.length ? item.venues.join(', ') : 'Venue not assigned yet'}</dd></div>
      </dl>
      <div className="attendee-card-actions"><WithdrawRegistration disabled={item.event_status === 'cancelled'} eventId={item.event_id} startDatetime={item.start_datetime} status={item.status}
        onWithdrawn={data => {
          setRegistrations(current => current.map(record => record.event_id === item.event_id
            ? { ...record, status: data.registration.status, withdrawn_at: data.registration.withdrawn_at } : record));
          setMessage(data.message);
          setRefresh(value => value + 1);
        }} /></div>
    </article>)}</div>
  </Container></>;
}
