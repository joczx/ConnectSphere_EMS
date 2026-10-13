import { useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';

const COLUMNS = [
  { status: 'submitted', label: 'Submitted', itemType: 'request' },
  { status: 'planning', label: 'Planning', itemType: 'event' },
  { status: 'pending_safety_checks', label: 'Pending Safety Checks', itemType: 'event' },
  { status: 'confirmed', label: 'Confirmed', itemType: 'event' },
];

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

function itemKey(item) {
  return `${item.item_type}:${item.item_type === 'request' ? item.event_request_id : item.event_id}`;
}

function endpoint(item) {
  return item.item_type === 'request'
    ? `/api/coordinator-lead/event-requests/${item.event_request_id}/coordinator`
    : `/api/coordinator-lead/events/${item.event_id}/coordinator`;
}

export default function ReassignEventCoordinators() {
  const { api } = useAuth();
  const [state, setState] = useState({
    loading: true,
    items: [],
    coordinators: [],
  });
  const [selected, setSelected] = useState({});
  const [busyKey, setBusyKey] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    api('/api/coordinator-lead/dashboard', { cache: 'no-store' })
      .then(data => {
        if (!ignore) {
          setState({
            loading: false,
            items: data.items || [],
            coordinators: data.coordinators || [],
          });
        }
      })
      .catch(err => {
        if (!ignore) {
          setState({
            loading: false,
            items: [],
            coordinators: [],
            error: err.message || 'Unable to load events for reassignment.',
          });
        }
      });
    return () => { ignore = true; };
  }, [api]);

  async function reassign(item) {
    const key = itemKey(item);
    const coordinatorId = selected[key] || item.event_coordinator_id || '';
    if (!coordinatorId || coordinatorId === item.event_coordinator_id) return;

    setBusyKey(key);
    setError('');
    setMessage('');
    try {
      const result = await api(endpoint(item), {
        method: 'PATCH',
        body: { coordinator_id: coordinatorId },
      });
      const coordinator = state.coordinators.find(user => user.id === coordinatorId);
      setState(current => ({
        ...current,
        items: current.items.map(existing => itemKey(existing) === key
          ? {
            ...existing,
            event_coordinator_id: coordinatorId,
            event_coordinator_name: coordinator?.name || 'Assigned Event Coordinator',
          }
          : existing),
      }));
      setSelected(current => ({ ...current, [key]: coordinatorId }));
      setMessage(result.message || 'Event Coordinator reassigned successfully.');
    } catch (err) {
      setError(err.message || 'Unable to reassign this Event Coordinator.');
    } finally {
      setBusyKey('');
    }
  }

  return <>
    <Navbar />
    <main className="container coordinator-dashboard">
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>Reassign Event Coordinators</h1></div></div>
      {state.loading && <p role="status">Loading events…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {error && <div role="alert" className="panel error">{error}</div>}
      {message && <p role="status" className="assignment-success">{message}</p>}
      {!state.loading && !state.error && state.coordinators.length === 0 && (
        <div role="alert" className="panel error">
          No users with the Event Coordinator role are available to assign.
        </div>
      )}
      {!state.loading && !state.error && COLUMNS.map(column => {
          const items = state.items.filter(item =>
            item.status === column.status && item.item_type === column.itemType);
          return <section key={column.status}>
            <h2>{column.label}</h2>
            {items.length > 0
              ? <div className="event-list">{items.map(item => {
                const key = itemKey(item);
                const coordinatorId = selected[key] ?? item.event_coordinator_id ?? '';
                const unchanged = coordinatorId === (item.event_coordinator_id || '');
                return <article className="panel coordinator-event-card" key={key}>
                  <h2>{item.event_name || 'Untitled event'}</h2>
                  <p className="metadata">Status: {column.label}</p>
                  <dl>
                    <div><dt>Purpose</dt><dd>{item.purpose || 'Not specified'}</dd></div>
                    <div><dt>Event Organiser</dt><dd>{item.event_organiser_name || 'Not specified'}</dd></div>
                    <div><dt>Starts</dt><dd>{date(item.start_datetime)}</dd></div>
                    <div><dt>Ends</dt><dd>{date(item.end_datetime)}</dd></div>
                    <div><dt>Expected attendance</dt><dd>{item.capacity_needed ?? 'Not specified'}</dd></div>
                    <div><dt>Event Coordinator</dt><dd>{item.event_coordinator_name || 'Unassigned'}</dd></div>
                  </dl>
                  <label htmlFor={`coordinator-${key}`}>
                    Reassign Event Coordinator
                    <select
                      id={`coordinator-${key}`}
                      value={coordinatorId}
                      onChange={event => setSelected(current => ({
                        ...current,
                        [key]: event.target.value,
                      }))}
                      disabled={busyKey === key || state.coordinators.length === 0}
                    >
                      <option value="">Choose a coordinator</option>
                      {state.coordinators.map(coordinator => (
                        <option key={coordinator.id} value={coordinator.id}>
                          {coordinator.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    disabled={!coordinatorId || unchanged || busyKey === key}
                    onClick={() => reassign(item)}
                  >
                    {busyKey === key ? 'Saving…' : 'Save reassignment'}
                  </button>
                </article>;
              })}</div>
              : <p>No events in this stage.</p>}
          </section>;
        })}
    </main>
  </>;
}
