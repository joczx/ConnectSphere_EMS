import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

function date(value) {
  return value ? new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(value)) : 'Not specified';
}
function Detail({ label, value }) {
  return <div><dt>{label}</dt><dd>{value === null || value === undefined || value === '' ? 'Not specified' : value}</dd></div>;
}

export default function Events({ token, onSignOut }) {
  const { eventId } = useParams();
  const [state, setState] = useState({ loading: true });
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState({ loading: true });
      try {
        const response = await fetch('/api/events' + (eventId ? '/' + encodeURIComponent(eventId) : ''), {
          headers: { Authorization: 'Bearer ' + token }, cache: 'no-store', signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(response.status === 401 ? 'Your session has expired. Sign out and sign in again.' : data.error);
        if (!controller.signal.aborted) setState({ data, key: eventId });
      } catch (err) {
        if (!controller.signal.aborted) setState({ error: err.message || 'Unable to load event information.' });
      }
    }
    load();
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [eventId, token, refresh]);
  const data = state.key === eventId ? state.data : null;
  const event = data?.event;
  return <>
    <header><Link className="brand" to="/events">ConnectSphere</Link><button className="secondary" onClick={onSignOut}>Sign out</button></header>
    <main className="container">
      {eventId && <Link to="/events">← My events</Link>}
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{eventId ? 'Event information' : 'My events'}</h1></div>
        <button className="secondary" onClick={() => setRefresh(value => value + 1)} disabled={state.loading}>Refresh</button></div>
      <p>All times are in Singapore time (SGT). Information refreshes every minute and when you return to this window.</p>
      {state.loading && <p role="status">Loading latest information…</p>}
      {state.error && <div role="alert" className="panel error">{state.error} Use Refresh to try again.</div>}
      {data?.events && <section className="event-list" aria-label="Your events">
        {data.events.length === 0 && <div className="panel">No events are available to you yet. Contact your event organiser or coordinator to arrange access.</div>}
        {data.events.map(item => <Link className="panel event-link" key={item.event_id} to={'/events/' + item.event_id}><h2>{item.event_name}</h2><p>{date(item.starts_at)}</p><span>View event information →</span></Link>)}
      </section>}
      {event && <article className="panel">
        <h2>{event.event_name}</h2><p className="metadata">Version {event.version} · Last updated {date(event.updated_at)}</p>
        <dl>
          <Detail label="Purpose" value={event.purpose} />
          <Detail label="Description" value={event.description} />
          <Detail label="Start date and time" value={date(event.starts_at)} />
          <Detail label="End date and time" value={date(event.ends_at)} />
          <Detail label="Expected attendance" value={event.expected_attendance} />
          <Detail label="Venue requirements" value={event.venue_requirements} />
          <Detail label="Accessibility needs" value={event.accessibility_needs} />
          <Detail label="Equipment requirements" value={event.equipment_requirements} />
          <Detail label="Registration required" value={event.registration_required == null ? null : event.registration_required ? 'Yes' : 'No'} />
          {event.registration_required !== false && <Detail label="Registration needs" value={event.registration_needs} />}
        </dl>
      </article>}
    </main>
  </>;
}
