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
        {data.events.map(item => <Link className="panel event-link" key={item.event_id} to={'/events/' + item.event_id}><h2>{item.event_name}</h2><p>{date(item.start_datetime)}</p><p className="metadata">Status: {item.status || 'Not specified'}</p><span>View event information →</span></Link>)}
      </section>}
      {event && <article className="panel">
        <h2>{event.event_name}</h2>
        <dl>
          <Detail label="Status" value={event.status} />
          <Detail label="Start date and time" value={date(event.start_datetime)} />
          <Detail label="End date and time" value={date(event.end_datetime)} />
          <Detail label="Event organiser ID" value={event.event_organiser_id} />
          <Detail label="Event coordinator ID" value={event.event_coordinator_id} />
          <Detail label="Technical support ID" value={event.technical_support_id} />
          <Detail label="Venue staff ID" value={event.venue_staff_id} />
        </dl>
      </article>}
    </main>
  </>;
}
