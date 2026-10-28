import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { formatDateTime, safetyStatusLabel } from '../services/operationalSafety';

export default function OperationalSafetyReviews() {
  const { api, can } = useAuth();
  const location = useLocation();
  const [state, setState] = useState({ loading: true, events: [] });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api('/api/operational-safety-reviews', { cache: 'no-store', signal: controller.signal }),
      api('/api/events', { cache: 'no-store', signal: controller.signal, feedback: false }),
    ])
      .then(([data, eventData]) => {
        if (controller.signal.aborted) return;
        // Only events this Safety Officer is assigned to.
        const assigned = new Set((eventData.events || [])
          .filter(event => can('safety.decide', event)).map(event => String(event.event_id)));
        setState({ loading: false, events: (data.events || []).filter(event => assigned.has(String(event.event_id))) });
      })
      .catch(error => { if (!controller.signal.aborted) setState({ loading: false, events: [], error: error.message || 'Unable to load safety reviews.' }); });
    return () => controller.abort();
  }, [api, can]);

  return <>
    <Navbar />
    <main className="container">
    <div className="heading"><div><p className="eyebrow">SAFETY MANAGEMENT</p><h1>Operational safety reviews</h1></div></div>
    <p>Events shown here are assigned to you and have been submitted by their Event Coordinator for a safety check once their venue and technical arrangements were confirmed.</p>
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
  </main>
  </>;
}
