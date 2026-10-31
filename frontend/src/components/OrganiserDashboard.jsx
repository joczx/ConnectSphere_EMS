import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { loadOrganiserDashboard } from '../services/organiserDashboard';
import { registrationDate } from './RegistrationPeriod';

const statuses = [['draft', 'Draft'], ['submitted', 'Submitted'], ['planning', 'Planning'], ['pending_safety_checks', 'Pending safety checks'],
  ['confirmed', 'Confirmed'], ['completed', 'Completed'], ['rejected', 'Rejected'], ['cancelled', 'Cancelled']];

export default function OrganiserDashboard() {
  const { api, userId } = useAuth();
  const [state, setState] = useState({ loading: true });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    loadOrganiserDashboard(api, userId, controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ ...data, loading: false }); })
      .catch(error => { if (!controller.signal.aborted) setState({ error: error.message, loading: false }); });
    const reload = () => setRevision(value => value + 1);
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, userId, revision]);
  return <section className="dashboard-overview" aria-label="Event organiser dashboard">
    <div className="dashboard-toolbar"><div><p className="eyebrow">YOUR EVENTS AT A GLANCE</p>
      <p className="metadata">{state.updatedAt ? `Updated ${registrationDate(state.updatedAt)}` : 'Loading current information'} · Refreshes every minute</p></div>
      <div className="event-reference-actions"><Link className="button-link secondary" to="/events">View my events</Link>
        <button type="button" className="secondary" disabled={state.loading} onClick={() => setRevision(value => value + 1)}>Refresh dashboard</button></div>
    </div>
    {state.loading && <p role="status">Loading your dashboard...</p>}
    {state.error && <p role="alert" className="panel error">{state.error}</p>}
    {state.warnings?.map(warning => <p role="alert" className="panel error" key={warning}>{warning} Refresh to retry.</p>)}
    {!state.loading && !state.error && <>
      <div className="organiser-status-grid">{statuses.map(([status, label]) => <article className="panel organiser-status-card" key={status}>
        <h2>{label}</h2><strong className={state.counts ? undefined : 'is-unavailable'}>{state.counts ? state.counts[status] || 0 : 'Unavailable'}</strong>
      </article>)}</div>
      <div className="dashboard-details">
        <section className="panel"><h2>Needs attention</h2>
          {!state.attention.length ? <p>{state.counts ? 'No outstanding actions for your events.' : 'Actions may be incomplete. Refresh to retry.'}</p>
            : <ul className="dashboard-action-list">{state.attention.map(item => <li key={item.key}>
              <Link to={item.path}><strong>{item.action}</strong><span>{item.name}</span></Link>
            </li>)}</ul>}
        </section>
        <section className="panel"><h2>Registration summary</h2><p className="metadata">Totals for upcoming events you organise.</p>
          {!state.registrationSummary ? <p>Registration totals are unavailable. Refresh to retry.</p> : <dl className="dashboard-statuses">
            <div><dt>Confirmed attendees</dt><dd>{state.registrationSummary.confirmed}</dd></div>
            <div><dt>Waitlisted</dt><dd>{state.registrationSummary.waitlisted}</dd></div>
            <div><dt>Withdrawn</dt><dd>{state.registrationSummary.withdrawn}</dd></div>
          </dl>}
        </section>
        <section className="panel organiser-upcoming"><h2>Upcoming events</h2><p className="metadata">Your next five events · Singapore time</p>
          {!state.eventsAvailable ? <p>Upcoming events are unavailable. Refresh to retry.</p> : !state.upcoming.length ? <p>No upcoming events.</p>
            : <ul className="organiser-event-list">{state.upcoming.map(event => <li key={event.event_id}>
              <div><Link to={`/events/${event.event_id}`}><strong>{event.event_name}</strong></Link>
                <p>{registrationDate(event.start_datetime)}</p>
                <p>Venue: {event.venues === null ? 'Unavailable' : event.venues.length ? event.venues.join(', ') : event.venue_name || 'Not assigned yet'}</p></div>
              <div>{event.registrations ? <p>{event.registrations.confirmed} confirmed · {event.registrations.waitlisted} waitlisted · {event.registrations.withdrawn} withdrawn</p>
                : <p>Registration totals unavailable</p>}<Link to={`/events/${event.event_id}/registrations`}>View registration records</Link></div>
            </li>)}</ul>}
        </section>
        <section className="panel"><h2>Recent updates</h2>
          {state.updates === null ? <p>Updates are unavailable. Refresh to retry.</p> : !state.updates.length ? <p>No recent updates.</p>
            : <ul className="organiser-updates">{state.updates.map(item => <li key={item.notification_id || item.id}>
              <strong>{item.title}</strong><p>{item.body}</p><span>{registrationDate(item.created_at)}</span>
            </li>)}</ul>}
          <Link className="dashboard-open" to="/notifications">View all updates</Link>
        </section>
      </div>
    </>}
  </section>;
}
