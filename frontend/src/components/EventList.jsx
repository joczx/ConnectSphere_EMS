import { useState } from 'react';
import { Link } from 'react-router-dom';
const stages = ['planning', 'confirmed', 'completed', 'cancelled'];
const title = value => value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll('_', ' ') : 'Not specified';
const date = value => value ? new Intl.DateTimeFormat('en-SG', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore' }).format(new Date(value)) : 'Date not set';
export default function EventList({ events }) {
  const [query, setQuery] = useState('');
  const [stage, setStage] = useState('all');
  const [order, setOrder] = useState('soonest');
  const filtered = events.filter(event => (stage === 'all' || event.status === stage)
    && (event.event_name || '').toLowerCase().includes(query.trim().toLowerCase())).sort((a, b) => {
    const left = a.start_datetime ? new Date(a.start_datetime).getTime() : Infinity;
    const right = b.start_datetime ? new Date(b.start_datetime).getTime() : Infinity;
    if (left === Infinity || right === Infinity) return left === right ? 0 : left === Infinity ? 1 : -1;
    return order === 'soonest' ? left - right : right - left;
  });
  const groups = [
    ['Active events', filtered.filter(event => !['completed', 'cancelled'].includes(event.status))],
    ['Past and cancelled events', filtered.filter(event => ['completed', 'cancelled'].includes(event.status))],
  ];
  return <section aria-label="Your events">
    <div className="event-stage-filters" aria-label="Filter events by status">
      {['all', ...stages].map(status => <button type="button" key={status} className={stage === status ? 'event-stage-filter selected' : 'event-stage-filter'} aria-pressed={stage === status} onClick={() => setStage(status)}>
        {status === 'all' ? 'All events' : title(status)} <strong>{status === 'all' ? events.length : events.filter(event => event.status === status).length}</strong>
      </button>)}
    </div>
    <div className="event-list-tools">
      <label>Search events<input type="search" placeholder="Search by event name" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <label>Sort by<select value={order} onChange={e => setOrder(e.target.value)}><option value="soonest">Start date: earliest first</option><option value="latest">Start date: latest first</option></select></label>
    </div>
    <p role="status" className="metadata">Showing {filtered.length} of {events.length} events</p>
    {!events.length && <p className="panel">No events are available to you yet. Contact your event organiser or coordinator to arrange access.</p>}
    {events.length > 0 && !filtered.length && <div className="panel"><p>No events match your search and status filter.</p><button type="button" className="secondary" onClick={() => { setQuery(''); setStage('all'); }}>Clear filters</button></div>}
    {groups.map(([name, items]) => items.length > 0 && <section key={name} className="event-list-group"><h2>{name} <span className="metadata">({items.length})</span></h2>
      <div className="event-catalogue">{items.map(event => <Link className="panel event-catalogue-card" key={event.event_id} to={'/events/' + event.event_id}>
        <span className={'event-stage event-stage-' + event.status}>{title(event.status)}</span>
        <h3>{event.event_name || 'Untitled event'}</h3>
        <dl><div><dt>Starts</dt><dd>{date(event.start_datetime)}</dd></div><div><dt>Ends</dt><dd>{date(event.end_datetime)}</dd></div></dl>
        <span className="event-card-open">View event ?</span>
      </Link>)}</div>
    </section>)}
  </section>;
}
