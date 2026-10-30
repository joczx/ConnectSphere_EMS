import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { formatDateTime, present, safetyStatusLabel } from '../services/operationalSafety';

function Detail({ label, children }) {
  return <div className="safety-review-item"><dt>{label}</dt><dd>{children}</dd></div>;
}

function list(items, empty = 'None recorded') {
  return Array.isArray(items) && items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : empty;
}

export default function OperationalSafetyReview() {
  const { api, can } = useAuth();
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true });
  const [decision, setDecision] = useState({ remarks: '', affected_arrangements: [], busy: false, error: '' });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api(`/api/operational-safety-reviews/${encodeURIComponent(eventId)}`, { cache: 'no-store', signal: controller.signal }),
      api(`/api/events/${encodeURIComponent(eventId)}`, { cache: 'no-store', signal: controller.signal, feedback: false }),
    ])
      .then(([data, eventData]) => {
        if (controller.signal.aborted) return;
        // Only the Safety Officer assigned to this event reviews it.
        if (!can('safety.decide', eventData.event || null)) {
          setState({ loading: false, error: 'Event not found or access unavailable.' });
          return;
        }
        setState({ loading: false, event: data.event });
      })
      .catch(error => { if (!controller.signal.aborted) setState({ loading: false, error: error.message || 'Unable to load this safety review.' }); });
    return () => controller.abort();
  }, [api, can, eventId]);

  const event = state.event;
  function toggleArrangement(value) {
    setDecision(current => ({ ...current, affected_arrangements: current.affected_arrangements.includes(value)
      ? current.affected_arrangements.filter(item => item !== value)
      : [...current.affected_arrangements, value] }));
  }
  async function decide(outcome) {
    if (outcome !== 'approved' && !decision.remarks.trim()) {
      setDecision(current => ({ ...current, error: 'Add remarks explaining what was not fulfilled or what must change.' }));
      return;
    }
    setDecision(current => ({ ...current, busy: true, error: '' }));
    try {
      const result = await api(`/api/operational-safety-reviews/${encodeURIComponent(eventId)}/decision`, {
        method: 'POST', body: { outcome, remarks: decision.remarks, affected_arrangements: decision.affected_arrangements },
      });
      navigate('/operational-safety-reviews', { replace: true, state: { message: result.message } });
    } catch (error) {
      setDecision(current => ({ ...current, busy: false, error: error.message || 'Unable to record the safety decision.' }));
    }
  }
  return <>
    <Navbar />
    <main className="container">
    <Link to="/operational-safety-reviews">← Operational safety reviews</Link>
    {state.loading && <p role="status">Loading safety arrangements…</p>}
    {state.error && <div className="panel error" role="alert">{state.error}</div>}
    {event && <>
      <div className="heading"><div><p className="eyebrow">SAFETY MANAGEMENT</p><h1>{event.event_name || 'Unnamed event'}</h1></div><span className="safety-status">{safetyStatusLabel}</span></div>
      <p>{formatDateTime(event.start_datetime)} – {formatDateTime(event.end_datetime)}</p>
      <section className="panel" aria-label="Operational safety arrangements">
        <h2>Safety review information</h2>
        <dl className="safety-review-details">
          <Detail label="Expected attendance">{present(event.expected_attendance)}</Detail>
          <Detail label="Venue capacity and layout">{present(event.venue_name)}<br />Capacity: {present(event.venue_capacity)}<br />Layout: {present(event.room_layout)}</Detail>
          <Detail label="Emergency access">{present(event.emergency_access)}</Detail>
          <Detail label="Accessibility requirements">{list(event.accessibility_requirements)}</Detail>
          <Detail label="Equipment placement">{list(event.equipment_placement)}</Detail>
          <Detail label="Crowd movement">{present(event.crowd_movement)}</Detail>
          <Detail label="Known venue restrictions">{present(event.venue_restrictions)}</Detail>
        </dl>
      </section>
      {can('safety.decide') && <section className="panel safety-decision" aria-label="Record safety decision">
        <h2>Safety decision</h2>
        <p>Approve only when the arrangements are safe. Reject with clear remarks describing what the Event Coordinator must change.</p>
        <fieldset disabled={decision.busy}>
          <label>
            Remarks and required follow-up
            <textarea rows="4" maxLength="2000" value={decision.remarks} onChange={event => setDecision(current => ({ ...current, remarks: event.target.value, error: '' }))} />
          </label>
          <fieldset className="safety-arrangements">
            <legend>Which arrangements are affected? <span className="metadata">(select when applicable)</span></legend>
            <label><input type="checkbox" checked={decision.affected_arrangements.includes('venue')} onChange={() => toggleArrangement('venue')} /> Venue arrangement</label>
            <label><input type="checkbox" checked={decision.affected_arrangements.includes('technical')} onChange={() => toggleArrangement('technical')} /> Technical arrangement</label>
          </fieldset>
          {decision.error && <p className="error" role="alert">{decision.error}</p>}
          <div className="safety-decision-actions">
            <button type="button" className="secondary" onClick={() => decide('rejected')}>Reject</button>
            <button type="button" onClick={() => decide('approved')}>{decision.busy ? 'Saving…' : 'Approve and confirm event'}</button>
          </div>
        </fieldset>
      </section>}
    </>}
  </main>
  </>;
}
