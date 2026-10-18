import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { importanceLabel, reviewApi, statusLabel } from '../services/eventChangeRequests';

const FIELD_LABELS = {
  event_name: 'Event name', description: 'Description', start_datetime: 'Start date and time',
  end_datetime: 'End date and time', capacity_needed: 'Expected attendance', room_layout: 'Room layout',
  required_facilities: 'Venue requirements', need_wheelchair_accessibility: 'Wheelchair accessibility',
  need_blind_accessibility: 'Accessibility for blind attendees', equipment_requirements: 'Equipment requirements',
};

export default function ReviewEventChangeRequests() {
  const { api } = useAuth();
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    const controller = new AbortController();
    reviewApi(api, '', { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted) setState({ requests: data.change_requests || [] }); })
      .catch(error => { if (!controller.signal.aborted) setState({ error: error.message || 'Unable to load change requests.' }); });
    return () => controller.abort();
  }, [api]);

  const requests = state.requests || [];
  return <>
    <Navbar />
    <main className="container">
      <Link to="/home">← Home</Link>
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>Review event change requests</h1></div></div>
      <p>Review critical changes requested for events assigned to you. Non-critical changes remain visible as history.</p>
      {state.loading && <p role="status">Loading change requests…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {!state.loading && !state.error && requests.length === 0 && <p className="panel">No change requests</p>}
      {requests.length > 0 && <div className="event-list change-request-list">{requests.map(item => (
        <Link className="panel event-link change-request-card" key={item.event_change_request_id} to={`/review-event-change-requests/${item.event_change_request_id}`}>
          <div className="change-request-tags">
            <span className={`change-request-tag change-request-${item.importance}`}>{importanceLabel(item.importance)}</span>
            <span className={`change-request-tag change-request-${item.status}`}>{statusLabel(item.status)}</span>
          </div>
          <h2>{item.event_name}</h2>
          <p className="metadata">Changed: {(item.changed_fields || []).map(field => FIELD_LABELS[field] || field).join(', ')}</p>
          <p className="metadata">Submitted {new Date(item.submitted_at).toLocaleString()}</p>
          <span>{item.status === 'pending_review' ? 'Review request →' : 'View request →'}</span>
        </Link>
      ))}</div>}
    </main>
  </>;
}

