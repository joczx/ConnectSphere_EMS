import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import { useAuth } from '../auth/AuthContext';

function ReviewForm({ request, onReviewed }) {
  const { api } = useAuth();
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const reservation = request.linked_reservation;
  async function decide(outcome) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await api(`/api/equipment-request-reviews/${request.equipment_request_id}`, {
        method: 'POST', body: { outcome, equipment_id: reservation?.equipment_id, reason },
      });
      onReviewed(result.equipment_request);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div>
    {reservation ? <p>Linked reservation: {reservation.quantity} units.</p> : <p>Reserve the full requested quantity on the <Link to="/reserved-equipment">Reserved Equipment page</Link>, then return here to accept.</p>}
    <button type="button" disabled={busy || !reservation || reservation.quantity !== request.quantity} onClick={() => decide('accepted')}>Accept request</button>
    <label>Reason for rejection<textarea value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label>
    {reservation && <p>Cancel the linked reservation on the Reserved Equipment page before rejecting.</p>}
    <button type="button" className="secondary" disabled={busy || !!reservation || !reason.trim()} onClick={() => decide('rejected')}>Reject request</button>
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

export default function Equipment() {
  const { api } = useAuth();
  const [requests, setRequests] = useState([]);
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    api('/api/equipment-request-reviews', { cache: 'no-store', signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return;
      setRequests(result.equipment_requests);
      setEvents(result.events);
    }).catch(err => {
      if (!controller.signal.aborted) { setError(err.message); setRequests([]); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    const focus = () => setRefresh(value => value + 1);
    window.addEventListener('focus', focus);
    return () => { controller.abort(); window.removeEventListener('focus', focus); };
  }, [api, refresh]);

  const groups = events.map(event => [String(event.event_id), event.event_name]);
  function reviewed(row) {
    setRequests(rows => rows.map(current => current.equipment_request_id === row.equipment_request_id ? { ...current, ...row } : current));
    setMessage('Decision saved. The event page now shows the updated equipment request.');
  }

  return <>
    <Navbar />
    <main className="container">
      <Link to="/home">Home</Link>
      <div className="heading"><div><p className="eyebrow">EQUIPMENT</p><h1>Equipment Requests</h1></div>
        <div><Link className="button-link" to="/reserved-equipment">Reserved Equipment</Link><button className="secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh</button></div></div>
      <p>Review coordinator requests. Reserve equipment on the Reserved Equipment page before accepting in full. Only events assigned to you for technical support appear here.</p>
      {error && <p role="alert" className="panel error">{error}</p>}
      {message && <p role="status" className="panel">{message}</p>}
      <label>Event<select value={eventId} onChange={e => setEventId(e.target.value)}>
        <option value="">All my events</option>{groups.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      {loading ? <p role="status">Loading equipment requests...</p> : <>
        {!requests.length && !error && <p>No equipment requests are assigned to you yet.</p>}
        {groups.filter(([id]) => !eventId || eventId === id).map(([id, name]) => <section key={id} className="panel" style={{ marginTop: '24px' }}>
          <div className="heading"><h2>{name}</h2><Link to={`/events/${id}`}>View event</Link></div>
          {!requests.some(row => String(row.event_id) === id) && <p>No equipment requests for this event yet.</p>}
          {requests.filter(row => String(row.event_id) === id).map(row => <article key={row.equipment_request_id} className="panel">
            <h3>{row.equipment_type}</h3>
            <EquipmentRequestStatus request={row} />
            {row.technical_requirements && <p>Technical requirements: {row.technical_requirements}</p>}
            {row.status === 'pending' && <ReviewForm request={row} onReviewed={reviewed} />}
          </article>)}
        </section>)}
      </>}
    </main>
  </>;
}
