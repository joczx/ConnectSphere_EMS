import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import { useAuth } from '../auth/AuthContext';

function ReviewForm({ request, equipment, onReviewed }) {
  const { api } = useAuth();
  const [outcome, setOutcome] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const matching = equipment.filter(item => item.equipment_type.trim().toLowerCase() === request.equipment_type.trim().toLowerCase());

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    const amount = Number(quantity);
    if (outcome === 'partially_accepted' && (!Number.isInteger(amount) || amount < 1 || amount >= request.quantity)) {
      setError('Enter a quantity greater than zero and less than the requested quantity.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await api(`/api/equipment-request-reviews/${request.equipment_request_id}`, {
        method: 'POST', body: { outcome, equipment_id: Number(equipmentId), accepted_quantity: amount, reason },
      });
      onReviewed(result.equipment_request);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <div>
    {!outcome ? <div className="heading">
      <button onClick={() => setOutcome('accepted')}>Accept</button>
      <button className="secondary" disabled={request.quantity <= 1} onClick={() => setOutcome('partially_accepted')}>Partially accept</button>
      <button className="secondary" onClick={() => setOutcome('rejected')}>Reject</button>
    </div> : <form onSubmit={submit}>
      <h4>{outcome === 'accepted' ? 'Accept request' : outcome === 'rejected' ? 'Reject request' : 'Partially accept request'}</h4>
      {outcome !== 'rejected' && <>
        <label>Equipment model<select required value={equipmentId} disabled={busy} onChange={e => setEquipmentId(e.target.value)}>
          <option value="">Select equipment</option>{matching.map(item => <option key={item.equipment_id} value={item.equipment_id}>{item.equipment_model}</option>)}
        </select></label>
        {!matching.length && <p>No matching equipment is in the catalogue.</p>}
        {outcome === 'partially_accepted' ? <label>Quantity to accept<input autoFocus type="number" required min="1" max={request.quantity - 1} step="1" value={quantity} disabled={busy} onChange={e => setQuantity(e.target.value)} /></label>
          : <p>Accept all {request.quantity} requested units.</p>}
      </>}
      {outcome === 'rejected' && <label>Reason for rejection<textarea required value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label>}
      {error && <p role="alert" className="error">{error}</p>}
      <button disabled={busy || (outcome !== 'rejected' && !equipmentId)}>{busy ? 'Saving...' : 'Confirm decision'}</button>
      <button type="button" className="secondary" disabled={busy} onClick={() => { setOutcome(''); setError(''); }}>Cancel</button>
    </form>}
  </div>;
}

export default function Equipment() {
  const { api } = useAuth();
  const [requests, setRequests] = useState([]);
  const [events, setEvents] = useState([]);
  const [equipment, setEquipment] = useState([]);
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
      setEquipment(result.equipment);
      setEvents(result.events);
    }).catch(err => {
      if (!controller.signal.aborted) { setError(err.message); setRequests([]); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
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
      <div className="heading"><div><p className="eyebrow">EQUIPMENT</p><h1>Reserve equipment</h1></div>
        <button className="secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh</button></div>
      <p>View your events and review equipment requests submitted by your account.</p>
      {error && <p role="alert" className="panel error">{error}</p>}
      {message && <p role="status" className="panel">{message}</p>}
      <label>Event<select value={eventId} onChange={e => setEventId(e.target.value)}>
        <option value="">All my events</option>{groups.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      {loading ? <p role="status">Loading equipment requests...</p> : <>
        {!requests.length && !error && <p>You have not submitted any equipment requests yet.</p>}
        {groups.filter(([id]) => !eventId || eventId === id).map(([id, name]) => <section key={id} className="panel" style={{ marginTop: '24px' }}>
          <div className="heading"><h2>{name}</h2><Link to={`/events/${id}`}>View event</Link></div>
          {!requests.some(row => String(row.event_id) === id) && <p>No equipment requests for this event yet.</p>}
          {requests.filter(row => String(row.event_id) === id).map(row => <article key={row.equipment_request_id} className="panel">
            <h3>{row.equipment_type}</h3>
            <EquipmentRequestStatus request={row} />
            {row.technical_requirements && <p>Technical requirements: {row.technical_requirements}</p>}
            {row.status === 'pending' && <ReviewForm request={row} equipment={equipment} onReviewed={reviewed} />}
          </article>)}
        </section>)}
      </>}
    </main>
  </>;
}
