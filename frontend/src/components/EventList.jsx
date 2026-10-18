import { useAuth } from '../auth/AuthContext';
import UiIcon from './UiIcon';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
const stages = ['planning', 'confirmed', 'completed', 'cancelled'];
const title = value => value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll('_', ' ') : 'Not specified';
const date = value => value ? new Intl.DateTimeFormat('en-SG', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore' }).format(new Date(value)) : 'Date not set';
export default function EventList({ events }) {
  const { api } = useAuth();
  const [names, setNames] = useState({});
  const organiserIds = [...new Set(events.map(event => event.event_organiser_id).filter(Boolean))].sort().join(',');
  useEffect(() => {
    if (!organiserIds) return;
    const controller = new AbortController();
    api('/api/users?ids=' + encodeURIComponent(organiserIds), { signal: controller.signal, cache: 'no-store', feedback: false })
      .then(data => { if (!controller.signal.aborted) setNames(data.users || {}); })
      .catch(() => {});
    return () => controller.abort();
  }, [api, organiserIds]);
  const [query, setQuery] = useState('');
  const [stage, setStage] = useState('all');
  const [order, setOrder] = useState('soonest');
  const filtered = events.filter(event => (stage === 'all' || event.status === stage)
    && `${event.event_name || ''} ${event.purpose || ''}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a, b) => {
    const left = a.start_datetime ? new Date(a.start_datetime).getTime() : Infinity;
    const right = b.start_datetime ? new Date(b.start_datetime).getTime() : Infinity;
    if (left === Infinity || right === Infinity) return left === right ? 0 : left === Infinity ? 1 : -1;
    return order === 'soonest' ? left - right : right - left;
  });
  const counts = Object.fromEntries(stages.map(status => [status, events.filter(event => event.status === status).length]));
  const statuses = [...new Set([...stages.filter(status => counts[status]), ...events.map(event => event.status).filter(Boolean)])];
  const active = events.filter(event => !['completed', 'cancelled', 'rejected'].includes(event.status)).length;
  const attention = events.filter(event => ['planning', 'pending_safety_checks', 'safety_changes_required'].includes(event.status)).length;
  return <section className="events-reference-list" aria-label="Your events">
    <div className="events-stat-cards">
      {[['Total events', events.length, 'In your workspace', 'events'], ['Active', active, 'Currently in progress', 'check'], ['Needs attention', attention, 'Planning or checks pending', 'requests']].map(([text, number, detail, icon], index) => <div className="events-stat-card" key={text}>
        <span className={'events-stat-icon tone-' + index}><UiIcon name={icon} /></span><div><strong>{number}</strong> <span>{text}</span><p>{detail}</p></div>
      </div>)}
    </div>
    <div className="events-results-panel">
      <div className="events-results-toolbar">
        <div className="event-list-tools">
          <label className="events-search"><span className="sr-only">Search events</span><UiIcon name="search" /><input type="search" placeholder="Search by event name or purpose" value={query} onChange={e => setQuery(e.target.value)} /></label>
          <label className="events-sort">Sort by<select value={order} onChange={e => setOrder(e.target.value)}><option value="soonest">Date: earliest first</option><option value="latest">Date: latest first</option></select></label>
        </div>
        <div className="events-status-pills" aria-label="Filter events by status">
          {['all', ...statuses].map(status => <button type="button" key={status} className={stage === status ? 'selected' : ''} aria-pressed={stage === status} onClick={() => setStage(status)}>{status === 'all' ? 'All' : title(status)} <span>{status === 'all' ? events.length : events.filter(event => event.status === status).length}</span></button>)}
        </div>
      </div>
      <div className="events-result-count"><p role="status">Showing <strong>{filtered.length}</strong> of {events.length} events</p>{(query || stage !== 'all') && <button type="button" onClick={() => { setQuery(''); setStage('all'); }}>Clear filters</button>}</div>
      {!filtered.length ? <div className="events-empty"><UiIcon name="events" /><h2>{events.length ? 'No matching events' : 'No events yet'}</h2><p>{events.length ? 'Try a different search term or clear your filters.' : 'Events available to you will appear here.'}</p></div> :
        <div className="events-reference-cards">{filtered.map(event => <Link className="events-reference-card" key={event.event_id} to={'/events/' + event.event_id}>
          <div className="event-date-tile"><span>{event.start_datetime ? new Intl.DateTimeFormat('en-SG', { month: 'short', timeZone: 'Asia/Singapore' }).format(new Date(event.start_datetime)) : 'TBC'}</span><strong>{event.start_datetime ? new Intl.DateTimeFormat('en-SG', { day: 'numeric', timeZone: 'Asia/Singapore' }).format(new Date(event.start_datetime)) : '-'}</strong></div>
          <div className="event-reference-card-content"><div className="event-reference-card-heading"><div><p className="event-purpose">{event.purpose || 'Event'}</p><h2>{event.event_name || 'Untitled event'}</h2></div><span className={'event-stage event-stage-' + event.status}>{title(event.status)}</span></div>
            <div className="event-reference-meta"><span>{date(event.start_datetime)}</span><span>{event.capacity_needed ?? '-'} attendees</span></div>
            <div className="event-reference-footer"><span>Organised by <strong>{names[event.event_organiser_id] || '-'}</strong></span><span aria-hidden="true">&rarr;</span></div>
          </div>
        </Link>)}</div>}
    </div>
  </section>;
}
