import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

function date(value) {
  return value ? new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(value)) : 'Not specified';
}
function Detail({ label, value }) {
  return <div><dt>{label}</dt><dd>{value === null || value === undefined || value === '' ? 'Not specified' : value}</dd></div>;
}

export default function Events({ token, onSignOut }) {
  const { eventId } = useParams();
  const [state, setState] = useState({ loading: true });
  const [refresh, setRefresh] = useState(0);
  const [form, setForm] = useState({
    equipment_type: '',
    quantity: 1,
    technical_requirements: '',
  });
  const [submitState, setSubmitState] = useState({ message: '', error: '' });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState({ loading: true });
      try {
        const response = await fetch('/api/events' + (eventId ? '/' + encodeURIComponent(eventId) : ''), {
          headers: { Authorization: 'Bearer ' + token }, cache: 'no-store', signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(response.status === 401 ? 'Your session has expired. Sign out and sign in again.' : data.error);
        if (!controller.signal.aborted) setState({ data, key: eventId });
      } catch (err) {
        if (!controller.signal.aborted) setState({ error: err.message || 'Unable to load event information.' });
      }
    }
    load();
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [eventId, token, refresh]);

  useEffect(() => {
    if (!eventId) return;
    let ignore = false;
    async function loadEquipment() {
      try {
        const response = await fetch(`/api/events/${encodeURIComponent(eventId)}/equipment-requests`, {
          headers: { Authorization: 'Bearer ' + token }, cache: 'no-store',
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Unable to load equipment requests.');
        if (!ignore) setState((current) => ({ ...current, equipment: data.equipment_requests || [] }));
      } catch (err) {
        if (!ignore) setState((current) => ({ ...current, equipmentError: err.message || 'Unable to load equipment requests.' }));
      }
    }
    loadEquipment();
    return () => { ignore = true; };
  }, [eventId, token, refresh]);

  async function submitEquipmentRequest(event) {
    event.preventDefault();
    setSubmitState({ message: '', error: '' });

    try {
      const response = await fetch(`/api/events/${encodeURIComponent(eventId)}/equipment-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({
          equipment_type: form.equipment_type,
          quantity: Number(form.quantity),
          technical_requirements: form.technical_requirements,
        }),
      });
      const data = await response.json();
      // const text = await response.text();
      // console.log("Status:", response.status);
      // console.log("Response:", text);

      if (!response.ok) throw new Error(data.error || 'Unable to submit equipment request.');
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

  return <>
    <header><Link className="brand" to="/events">ConnectSphere</Link><button className="secondary" onClick={onSignOut}>Sign out</button></header>
    <main className="container">
      {eventId && <Link to="/events">← My events</Link>}
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{eventId ? 'Event information' : 'My events'}</h1></div>
        <button className="secondary" onClick={() => setRefresh(value => value + 1)} disabled={state.loading}>Refresh</button></div>
      <p>All times are in Singapore time (SGT). Information refreshes every minute and when you return to this window.</p>
      {state.loading && <p role="status">Loading latest information…</p>}
      {state.error && <div role="alert" className="panel error">{state.error} Use Refresh to try again.</div>}
      {data?.events && <section className="event-list" aria-label="Your events">
        {data.events.length === 0 && <div className="panel">No events are available to you yet. Contact your event organiser or coordinator to arrange access.</div>}
        {data.events.map(item => <Link className="panel event-link" key={item.event_id} to={'/events/' + item.event_id}><h2>{item.event_name}</h2><p>{date(item.start_datetime)}</p><p className="metadata">Status: {item.status || 'Not specified'}</p><span>View event information →</span></Link>)}
      </section>}
      {event && <article className="panel">
        <h2>{event.event_name}</h2>
        <dl>
          <Detail label="Status" value={event.status} />
          <Detail label="Start date and time" value={date(event.start_datetime)} />
          <Detail label="End date and time" value={date(event.end_datetime)} />
          <Detail label="Event organiser ID" value={event.event_organiser_id} />
          <Detail label="Event coordinator ID" value={event.event_coordinator_id} />
          <Detail label="Technical support ID" value={event.technical_support_id} />
          <Detail label="Venue staff ID" value={event.venue_staff_id} />
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
            <input value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} required />
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
                <p>Quantity: {item.quantity}</p>
                <p>Technical requirements: {item.technical_requirements || 'Not specified'}</p>
              </div>
            ))
          )}
        </div>
      </section>}
    </main>
  </>;
}
