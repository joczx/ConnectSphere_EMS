import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useFeedback } from '../components/FeedbackProvider';
import EquipmentRequestForm from '../components/EquipmentRequestForm';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import { useAuth } from '../auth/AuthContext';
import { loadEvents } from '../services/eventLoading';
import { statusLabel } from '../services/venueBookings';

// The Event Coordinator's side of equipment: request it for the events they
// coordinate and follow what Technical Support decided. Reviewing requests is
// Technical Support's page, /equipment.
export default function EquipmentRequests() {
  const { api, userId, can } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const eventId = searchParams.get('event_id') || '';
  const [state, setState] = useState({ loading: true, events: [], requests: [], error: '', warning: '' });
  const [refresh, setRefresh] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const { confirm } = useFeedback();

  useEffect(() => {
    const controller = new AbortController();
    setState(current => ({ ...current, loading: true, error: '' }));
    (async () => {
      try {
        const { data, statusWarning } = await loadEvents(api, '/api/events', { cache: 'no-store', signal: controller.signal });
        const events = (data.events || []).filter(event => event.event_coordinator_id === userId);
        const lists = await Promise.all(events.map(async event =>
          (await api(`/api/events/${encodeURIComponent(event.event_id)}/equipment-requests`, { cache: 'no-store', signal: controller.signal })).equipment_requests || []));
        if (!controller.signal.aborted) setState({ loading: false, events, requests: lists.flat(), error: '', warning: statusWarning });
      } catch (err) {
        if (!controller.signal.aborted) setState(current => ({ ...current, loading: false, error: err.message || 'Unable to load equipment requests.' }));
      }
    })();
    return () => controller.abort();
  }, [api, userId, refresh]);

  async function remove(id, row) {
    const accepted = await confirm(
      `Delete the request for ${row.quantity} × ${row.equipment_type}? Technical Support will no longer see it.`,
      { title: 'Delete equipment request', confirmLabel: 'Delete', cancelLabel: 'Keep', destructive: true },
    );
    if (!accepted) return;
    setBusyId(row.equipment_request_id);
    try {
      await api(`/api/events/${encodeURIComponent(id)}/equipment-requests/${encodeURIComponent(row.equipment_request_id)}`, { method: 'DELETE' });
    } catch {
      // api() has already shown the reason; refresh in case it was reviewed meanwhile.
    } finally {
      setBusyId(null);
      setRefresh(value => value + 1);
    }
  }

  function chooseEvent(id) {
    setSearchParams(id ? { event_id: id } : {}, { replace: true });
  }

  const shown = state.events.filter(event => !eventId || String(event.event_id) === eventId);

  return <>
    <Navbar />
    <main className="container">
      <Link to="/home">Home</Link>
      <div className="heading"><div><p className="eyebrow">EQUIPMENT</p><h1>Request Equipment</h1></div>
        <div><Link className="button-link secondary" to="/equipment-availability">Check availability</Link><button className="secondary" disabled={state.loading} onClick={() => setRefresh(value => value + 1)}>Refresh</button></div></div>
      <p>Request equipment for the events you coordinate and follow Technical Support&apos;s decisions. New requests can only be made while an event is in planning.</p>
      {state.warning && <p role="status" className="panel">{state.warning}</p>}
      {state.error && <p role="alert" className="panel error">{state.error}</p>}
      <label>Event<select value={eventId} onChange={e => chooseEvent(e.target.value)}>
        <option value="">All my events</option>
        {state.events.map(event => <option key={event.event_id} value={String(event.event_id)}>{event.event_name} — {statusLabel(event.status)}</option>)}
      </select></label>
      {state.loading && !state.events.length ? <p role="status">Loading equipment requests...</p> : <>
        {!state.events.length && !state.error && <p>You are not the coordinator of any events yet.</p>}
        {shown.map(event => {
          const id = String(event.event_id);
          const requests = state.requests.filter(row => String(row.event_id) === id);
          return <section key={id} className="panel" style={{ marginTop: '24px' }}>
            <div className="heading"><h2>{event.event_name}</h2><Link to={`/events/${id}`}>View event</Link></div>
            <p className="metadata"><span className={'event-stage event-stage-' + event.status}>{statusLabel(event.status)}</span></p>
            {event.status === 'planning' && can('equipment.request', event)
              ? <EquipmentRequestForm eventId={id} onSubmitted={() => setRefresh(value => value + 1)} />
              : <p className="metadata">Equipment can only be requested while the event is in planning.</p>}
            {!requests.length && <p>No equipment requests for this event yet.</p>}
            {requests.map(row => {
              // Technical Support may decide at any moment; once they have,
              // the request is part of the record and is no longer editable.
              const changeable = row.status === 'pending' && event.status === 'planning' && can('equipment.request', event);
              return <article key={row.equipment_request_id} className="panel" style={{ marginTop: '12px' }}>
                {editingId === row.equipment_request_id
                  ? <EquipmentRequestForm eventId={id} request={row} onCancel={() => setEditingId(null)}
                      onSubmitted={() => { setEditingId(null); setRefresh(value => value + 1); }} />
                  : <>
                    <h3>{row.equipment_type}</h3>
                    <EquipmentRequestStatus request={row} />
                    <p>Technical requirements: {row.technical_requirements || 'Not specified'}</p>
                    {changeable && <div>
                      <button type="button" className="secondary" disabled={busyId !== null} onClick={() => setEditingId(row.equipment_request_id)}>Edit</button>
                      <button type="button" className="danger-button" disabled={busyId !== null} onClick={() => remove(id, row)}>Delete</button>
                    </div>}
                  </>}
              </article>;
            })}
          </section>;
        })}
      </>}
    </main>
  </>;
}
