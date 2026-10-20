import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EquipmentRequestForm from '../components/EquipmentRequestForm';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import { useAuth } from '../auth/AuthContext';
import { loadEvents } from '../services/eventLoading';
import { statusLabel } from '../services/venueBookings';
import { userId } from '../services/eventRequests';

// The Event Coordinator's side of equipment: request it for the events they
// coordinate and follow what Technical Support decided. Reviewing requests is
// Technical Support's page, /equipment.
export default function EquipmentRequests() {
  const { api, token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const eventId = searchParams.get('event_id') || '';
  const [state, setState] = useState({ loading: true, events: [], requests: [], error: '', warning: '' });
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const me = token ? userId(token) : null;
    setState(current => ({ ...current, loading: true, error: '' }));
    (async () => {
      try {
        const { data, statusWarning } = await loadEvents(api, '/api/events', { cache: 'no-store', signal: controller.signal });
        const events = (data.events || []).filter(event => event.event_coordinator_id === me);
        const lists = await Promise.all(events.map(async event =>
          (await api(`/api/events/${encodeURIComponent(event.event_id)}/equipment-requests`, { cache: 'no-store', signal: controller.signal })).equipment_requests || []));
        if (!controller.signal.aborted) setState({ loading: false, events, requests: lists.flat(), error: '', warning: statusWarning });
      } catch (err) {
        if (!controller.signal.aborted) setState(current => ({ ...current, loading: false, error: err.message || 'Unable to load equipment requests.' }));
      }
    })();
    return () => controller.abort();
  }, [api, token, refresh]);

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
            {event.status === 'planning'
              ? <EquipmentRequestForm eventId={id} onSubmitted={() => setRefresh(value => value + 1)} />
              : <p className="metadata">Equipment can only be requested while the event is in planning.</p>}
            {!requests.length && <p>No equipment requests for this event yet.</p>}
            {requests.map(row => <article key={row.equipment_request_id} className="panel" style={{ marginTop: '12px' }}>
              <h3>{row.equipment_type}</h3>
              <EquipmentRequestStatus request={row} />
              <p>Technical requirements: {row.technical_requirements || 'Not specified'}</p>
            </article>)}
          </section>;
        })}
      </>}
    </main>
  </>;
}
