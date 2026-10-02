import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import { useAuth } from '../auth/AuthContext';

function date(value) {
  return value ? new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(value)) : 'Not specified';
}
function Detail({ label, value }) {
  return <div><dt>{label}</dt><dd>{value === null || value === undefined || value === '' ? 'Not specified' : value}</dd></div>;
}

export default function Events() {
  const { api } = useAuth();
  const { eventId } = useParams();
  const [state, setState] = useState({ loading: true });
  const [refresh, setRefresh] = useState(0);
  const [form, setForm] = useState({
    equipment_type: '',
    quantity: 1,
    technical_requirements: '',
  });
  const [submitState, setSubmitState] = useState({ message: '', error: '' });
  const [userNames, setUserNames] = useState({});
  const [coordinatorChoices, setCoordinatorChoices] = useState([]);
  const [reassignForm, setReassignForm] = useState({ open: false, value: '', busy: false, error: '', message: '' });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState((current) => ({ ...current, loading: true, error: null }));
      try {
        const path = '/api/events' + (eventId ? '/' + encodeURIComponent(eventId) : '');
        const data = await api(path, { cache: 'no-store', signal: controller.signal });
        if (!controller.signal.aborted) setState((current) => ({ ...current, data, key: eventId, loading: false, error: null }));
      } catch (err) {
        if (!controller.signal.aborted) setState((current) => ({ ...current, loading: false, error: err.message || 'Unable to load event information.' }));
      }
    }
    load();
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, eventId, refresh]);

  useEffect(() => {
    if (!eventId) return;
    let ignore = false;
    async function loadEquipment() {
      try {
        const data = await api(`/api/events/${encodeURIComponent(eventId)}/equipment-requests`, { cache: 'no-store' });
        if (!ignore) setState((current) => ({ ...current, equipment: data.equipment_requests || [], equipmentError: null }));
      } catch (err) {
        if (!ignore) setState((current) => ({ ...current, equipmentError: err.message || 'Unable to load equipment requests.' }));
      }
    }
    loadEquipment();
    return () => { ignore = true; };
  }, [api, eventId, refresh]);


  const [equipmentTypes, setEquipmentTypes] = useState([]);

  useEffect(() => {
    let ignore = false;
    api('/api/equipment-types', { cache: 'no-store' })
      .then(data => { if (!ignore) setEquipmentTypes(data.equipment_types || []); })
      .catch(err => { if (!ignore) setSubmitState({ message: '', error: err.message }); });
    return () => { ignore = true; };
  }, [api]);

  async function submitEquipmentRequest(event) {
    event.preventDefault();
    setSubmitState({ message: '', error: '' });

    try {
      const data = await api(`/api/events/${encodeURIComponent(eventId)}/equipment-requests`, {
        method: 'POST',
        body: {
          equipment_type: form.equipment_type,
          quantity: Number(form.quantity),
          technical_requirements: form.technical_requirements,
        },
      });
      setSubmitState({ message: data.message || 'Equipment request submitted successfully.', error: '' });
      setForm({ equipment_type: '', quantity: 1, technical_requirements: '' });
      setRefresh(value => value + 1);
    } catch (err) {
      setSubmitState({ message: '', error: err.message || 'Unable to submit equipment request.' });
    }
  }


  const data = state.key === eventId ? state.data : null;
  const event = data?.event;
  const equipmentRequests = state.equipment || [];

  useEffect(() => {
    if (!event) return;

    const ids = [
      event.event_organiser_id,
      event.event_coordinator_id,
      event.technical_support_id,
      event.venue_staff_id,
    ].filter(Boolean).join(',');

    if (ids) {
      api(`/api/users?ids=${encodeURIComponent(ids)}`, { cache: 'no-store' })
        .then((data) => setUserNames(data.users || {}))
        .catch(() => setUserNames({}));
    } else {
      setUserNames({});
    }

    api('/api/users?role=event_coordinator', { cache: 'no-store' })
      .then((data) => {
        const options = Object.entries(data.users || {}).map(([id, name]) => ({ id, name }));
        setCoordinatorChoices(options.filter(({ id }) => id !== event.event_coordinator_id));
      })
      .catch(() => setCoordinatorChoices([]));
  }, [api, event]);

  async function reassignCoordinator(eventSubmit) {
    eventSubmit.preventDefault();
    if (!event || !reassignForm.value) return;

    setReassignForm((current) => ({ ...current, busy: true, error: '', message: '' }));
    try {
      const data = await api(`/api/events/${encodeURIComponent(eventId)}/coordinator`, {
        method: 'PATCH',
        body: { event_coordinator_id: reassignForm.value },
      });
      setReassignForm({ open: false, value: '', busy: false, error: '', message: data.message || 'Coordinator reassigned.' });
      setRefresh(value => value + 1);
    } catch (err) {
      setReassignForm((current) => ({ ...current, busy: false, error: err.message || 'Unable to reassign the coordinator.' }));
    }
  }

  return <>
    <Navbar />
    <main className="container">
      {eventId && <Link to="/events">← My events</Link>}
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{eventId ? 'Event information' : 'My events'}</h1></div>
        <button className="secondary" onClick={() => setRefresh(value => value + 1)} disabled={state.loading}>Refresh</button></div>
      <p>All times are in Singapore time (SGT). Information refreshes every minute and when you return to this window.</p>
      {state.loading && <p role="status">Loading latest information…</p>}
      {state.error && <div role="alert" className="panel error">{state.error} Use Refresh to try again.</div>}
      {data?.events && <section className="event-list" aria-label="Your events">
        {data.events.length === 0 && <div className="panel">No events are available to you yet. Contact your event organiser or coordinator to arrange access.</div>}
        {data.events.map(item => <Link className="panel event-link" key={item.event_id} to={'/events/' + item.event_id}><h2>{item.event_name}</h2><p>{date(item.start_datetime)}</p><p className="metadata">Status: {item.status ? item.status.charAt(0).toUpperCase() + item.status.slice(1) : 'Not specified'}</p><span>View event information →</span></Link>)}
      </section>}
      {event && <article className="panel">
        <div className="heading" style={{ alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>{event.event_name}</h2>
          <button type="button" className="secondary" onClick={() => setReassignForm(current => ({ ...current, open: !current.open, value: '', error: '', message: '' }))}>Reassign Event Coordinator</button>
        </div>
        {reassignForm.message && <div className="success" style={{ marginBottom: '12px' }}>{reassignForm.message}</div>}
        {reassignForm.error && <div className="error" style={{ marginBottom: '12px' }}>{reassignForm.error}</div>}
        {reassignForm.open && <form onSubmit={reassignCoordinator} style={{ display: 'grid', gap: '12px', marginBottom: '20px' }}>
          <label>
            Replacement event coordinator
            <select value={reassignForm.value} onChange={(e) => setReassignForm((current) => ({ ...current, value: e.target.value }))} required>
              <option value="">Select an event coordinator</option>
              {coordinatorChoices.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}
            </select>
          </label>
          <button type="submit" disabled={reassignForm.busy}>{reassignForm.busy ? 'Reassigning…' : 'Save reassignment'}</button>
        </form>}
        <dl>
          <Detail label="Status" value={event.status ? event.status.charAt(0).toUpperCase() + event.status.slice(1) : null} />
          <Detail label="Start date and time" value={date(event.start_datetime)} />
          <Detail label="End date and time" value={date(event.end_datetime)} />
          <Detail label="Event organiser" value={userNames[event.event_organiser_id] || (event.event_organiser_id ? event.event_organiser_id.slice(0, 8) : 'Not specified')} />
          <Detail label="Event coordinator" value={userNames[event.event_coordinator_id] || (event.event_coordinator_id ? event.event_coordinator_id.slice(0, 8) : 'Not specified')} />
          <Detail label="Technical support" value={userNames[event.technical_support_id] || (event.technical_support_id ? event.technical_support_id.slice(0, 8) : 'Not specified')} />
          <Detail label="Venue staff" value={userNames[event.venue_staff_id] || (event.venue_staff_id ? event.venue_staff_id.slice(0, 8) : 'Not specified')} />
        </dl>
      </article>}

      {eventId && <section className="panel" style={{ marginTop: '24px' }}>
        <h2>Equipment requests</h2>
        {state.equipmentError && <div className="error">{state.equipmentError}</div>}
        {submitState.error && <div className="error">{submitState.error}</div>}
        {submitState.message && <div className="success">{submitState.message}</div>}

        <form onSubmit={submitEquipmentRequest} style={{ display: 'grid', gap: '12px', marginTop: '16px' }}>
          <label>
            Equipment Type
            {/* <input value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} required /> */}
            <select value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} required>
              <option value="">Select</option>
              {equipmentTypes.map(type => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <label>
            Quantity
            <input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required />
          </label>
          <label>
            Technical requirements
            <textarea value={form.technical_requirements} onChange={(e) => setForm({ ...form, technical_requirements: e.target.value })} rows="6" />
          </label>
          <button type="submit">Submit equipment request</button>
        </form>

        <div style={{ marginTop: '24px' }}>
          {equipmentRequests.length === 0 ? (
            <p>No equipment requests for this event yet.</p>
          ) : (
            equipmentRequests.map((item) => (
              <div key={item.equipment_request_id || item.id} className="panel" style={{ marginTop: '12px' }}>
                <h3>{item.equipment_type}</h3>
                <EquipmentRequestStatus request={item} />
                <p>Technical requirements: {item.technical_requirements || 'Not specified'}</p>
              </div>
            ))
          )}
        </div>
      </section>}
    </main>
  </>;
}
