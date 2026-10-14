import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { formatDateTime, safetyStatusLabel } from '../services/operationalSafety';

export default function OperationalSafetyReviews() {
  const { api } = useAuth();
  const location = useLocation();
  const [state, setState] = useState({ loading: true, events: [] });

  useEffect(() => {
    const controller = new AbortController();
    api('/api/operational-safety-reviews', { cache: 'no-store', signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setState({ loading: false, events: data.events || [] }); })
      .catch(error => { if (!controller.signal.aborted) setState({ loading: false, events: [], error: error.message || 'Unable to load safety reviews.' }); });
    return () => controller.abort();
  }, [api]);

  return <main className="container">
    <div className="heading"><div><p className="eyebrow">SAFETY MANAGEMENT</p><h1>Operational safety reviews</h1></div></div>
    <p>Events shown here have completed their venue and technical arrangements and are awaiting a safety check.</p>
    {location.state?.message && <p className="panel venue-success" role="status">{location.state.message}</p>}
    {state.loading && <p role="status">Loading events awaiting safety checks…</p>}
    {state.error && <div className="panel error" role="alert">{state.error}</div>}
    {!state.loading && !state.error && state.events.length === 0 && <div className="panel">No events are awaiting safety checks.</div>}
    <div className="event-list safety-review-list">
      {state.events.map(event => <Link className="panel event-link safety-review-card" key={event.event_id} to={`/operational-safety-reviews/${event.event_id}`}>
        <span className="safety-status">{safetyStatusLabel}</span>
        <h2>{event.event_name || 'Unnamed event'}</h2>
        <p>{formatDateTime(event.start_datetime)} – {formatDateTime(event.end_datetime)}</p>
        <p className="metadata">{event.capacity_needed || 'Attendance not recorded'} expected · {event.venue_name || 'Venue not recorded'}</p>
        <span>Review arrangements →</span>
      </Link>)}
    </div>
  </main>;
}
