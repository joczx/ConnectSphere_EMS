import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { userId } from '../services/eventRequests';
import { loadDashboard, upcomingEvents } from '../services/dashboard';

const formatDate = value => new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
}).format(new Date(value));
const pendingStatus = { 'own-requests': 'draft', 'review-requests': 'submitted', assignments: 'submitted', venues: 'submitted', equipment: 'pending' };

export default function DashboardOverview() {
  const { api, token, account } = useAuth();
  const roles = account.user?.roles || [];
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    loadDashboard(api, roles, userId(token), controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ ...data, loading: false }); })
      .catch(error => { if (!controller.signal.aborted) setState({ error: error.message, loading: false }); });
    const timer = setInterval(() => setRevision(value => value + 1), 60000);
    const focus = () => setRevision(value => value + 1);
    window.addEventListener('focus', focus);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', focus); };
  }, [api, token, account.user, revision]);
  const sections = state.sections || [];
  const next = upcomingEvents(state.events || []);
  const actions = sections.filter(section => section.counts[pendingStatus[section.id]] > 0);
  return <section className="dashboard-overview" aria-label="Your dashboard">
    <div className="dashboard-toolbar">
      <div><p className="eyebrow">{roles.join(' ? ') || 'Your account'}</p>
        <p className="metadata">{state.updatedAt ? `Updated ${formatDate(state.updatedAt)} (SGT)` : 'Loading current totals?'} ? Refreshes every minute</p></div>
      <button className="secondary" disabled={state.loading} onClick={() => setRevision(value => value + 1)}>Refresh dashboard</button>
    </div>
    {state.loading && <p role="status">Loading your dashboard?</p>}
    {state.error && <p role="alert" className="panel error">{state.error}</p>}
    {state.warnings?.map(warning => <p role="alert" className="panel error" key={warning}>{warning} Use Refresh dashboard to retry.</p>)}
    <div className="dashboard-metrics">{sections.map(section => <article className="panel dashboard-metric" key={section.id}>
      <div className="dashboard-metric-title"><h2><Link to={section.path}>{section.title}</Link></h2><strong aria-label={`${section.total} total`}>{section.total}</strong></div>
      <p className="metadata">{section.scope}</p>
      <p className="metadata">{section.reviewed !== null && `Reviewed: ${section.reviewed} ? Current decision outcomes`}</p>
      <dl className="dashboard-statuses">{section.statuses.map(([status, label]) => <div key={status}><dt>{label}</dt><dd>{section.counts[status] || 0}</dd></div>)}</dl>
      {Object.entries(section.counts).filter(([status]) => !section.statuses.some(([known]) => known === status)).map(([status, count]) => <p className="metadata" key={status}>{status.replaceAll('_', ' ')}: {count}</p>)}
      <Link className="dashboard-open" to={section.path}>Open {section.title.toLowerCase()} ?</Link>
    </article>)}</div>
    {!state.loading && sections.length > 0 && <div className="dashboard-details">
      <section className="panel"><h2>Needs attention</h2>
        {actions.length === 0 ? <p>No pending work in the loaded queues.</p> : <ul className="dashboard-action-list">{actions.map(section => <li key={section.id}><Link to={section.path}>
          <strong>{section.counts[pendingStatus[section.id]]}</strong> {section.id === 'own-requests' ? 'draft requests to finish' : section.id === 'assignments' ? 'requests to assign' : section.id === 'venues' && !roles.some(role => role.toLowerCase().replaceAll('_', ' ') === 'venue staff') ? 'venue requests awaiting a decision' : `${section.title.toLowerCase()} awaiting review`} ?
        </Link></li>)}</ul>}
        <p className="metadata">Counts show current stages. Approved event requests enter Planning; equipment decisions use Accepted and Partially accepted.</p>
      </section>
      <section className="panel"><h2>Upcoming events</h2><p className="metadata">Your next five active events ? Singapore time</p>
        {!sections.some(section => section.id === 'events') ? <p>Upcoming events are unavailable. Refresh to retry.</p> : next.length === 0 ? <p>No upcoming events.</p> : <ul className="dashboard-upcoming">{next.map(event => <li key={event.event_id}><Link to={'/events/' + event.event_id}>{event.event_name || 'Untitled event'}</Link>
          <span>{event.start_datetime && formatDate(event.start_datetime)} ? {event.status === 'confirmed' ? 'Confirmed' : 'Planning'}</span></li>)}</ul>}
      </section>
    </div>}
  </section>;
}
