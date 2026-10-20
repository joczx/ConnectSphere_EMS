import { useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';

function date(value) {
  if (!value) return 'Not specified';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Not specified';
  return new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Singapore',
  }).format(parsed);
}

export default function AssignEventCoordinators() {
  const { api, can } = useAuth();
  const [state, setState] = useState({ loading: true, requests: [], coordinators: [] });
  const [selected, setSelected] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    api('/api/event-requests/unassigned', { cache: 'no-store' })
      .then(data => {
        if (!ignore) setState({
          loading: false,
          requests: data.event_requests || [],
          coordinators: data.coordinators || [],
        });
      })
      .catch(err => {
        if (!ignore) setState({
          loading: false,
          requests: [],
          coordinators: [],
          error: err.message || 'Unable to load unassigned event requests.',
        });
      });
    return () => { ignore = true; };
  }, [api]);

  async function assign(eventRequestId) {
    setBusyId(eventRequestId);
    setError('');
    setMessage('');
    try {
      const result = await api(`/api/event-requests/${eventRequestId}/assign-coordinator`, {
        method: 'POST',
        body: { coordinator_id: selected[eventRequestId] },
      });
      setState(current => ({
        ...current,
        requests: current.requests.filter(
          item => item.event_request_id !== eventRequestId,
        ),
      }));
      setMessage(result.message || 'Event Coordinator assigned successfully.');
    } catch (err) {
      setError(err.message || 'Unable to assign the Event Coordinator.');
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <Navbar />
    <main className="container">
      <div className="heading">
        <div>
          <p className="eyebrow">EVENT PLANNING</p>
          <h1>Assign Event Coordinators</h1>
          <p>Assign each submitted request to an Event Coordinator to manage its planning.</p>
        </div>
      </div>
      {state.loading && <p role="status">Loading unassigned event requests…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {error && <div role="alert" className="panel error">{error}</div>}
      {message && <p role="status" className="assignment-success">{message}</p>}
      {!state.loading && !state.error && state.requests.length === 0 && (
        <p>No unassigned submitted event requests.</p>
      )}
      {!state.loading && state.coordinators.length === 0 && state.requests.length > 0 && (
        <div role="alert" className="panel error">
          No users with the Event Coordinator role are available to assign.
        </div>
      )}
      <div className="event-list assignment-list">
        {state.requests.map(item => (
          <article className="panel assignment-card" key={item.event_request_id}>
            <h2>{item.event_name}</h2>
            <dl>
              <div><dt>Purpose</dt><dd>{item.purpose || 'Not specified'}</dd></div>
              <div><dt>Event Organiser</dt><dd>{item.event_organiser_name || 'Not specified'}</dd></div>
              <div><dt>Starts</dt><dd>{date(item.start_datetime)}</dd></div>
              <div><dt>Ends</dt><dd>{date(item.end_datetime)}</dd></div>
              <div><dt>Expected attendance</dt><dd>{item.capacity_needed ?? 'Not specified'}</dd></div>
              <div><dt>Room layout</dt><dd>{item.room_layout || 'Not specified'}</dd></div>
            </dl>
            <label htmlFor={`coordinator-${item.event_request_id}`}>
              Assign to Event Coordinator
              <select
                id={`coordinator-${item.event_request_id}`}
                value={selected[item.event_request_id] || ''}
                onChange={event => setSelected(current => ({
                  ...current,
                  [item.event_request_id]: event.target.value,
                }))}
                disabled={busyId === item.event_request_id || !state.coordinators.length}
              >
                <option value="">Choose a coordinator</option>
                {state.coordinators.map(coordinator => (
                  <option key={coordinator.id} value={coordinator.id}>{coordinator.name}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={!can('eventRequest.assign') || !selected[item.event_request_id] || busyId === item.event_request_id}
              onClick={() => assign(item.event_request_id)}
            >
              {busyId === item.event_request_id ? 'Assigning…' : 'Assign coordinator'}
            </button>
          </article>
        ))}
      </div>
    </main>
  </>;
}
