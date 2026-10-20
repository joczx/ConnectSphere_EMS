import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function ReserveEquipment({ onReserved, refresh = 0 }) {
  const { api, can } = useAuth();
  const [events, setEvents] = useState([]);
  const [catalogue, setCatalogue] = useState([]);
  const [requests, setRequests] = useState([]);
  const [eventId, setEventId] = useState('');
  const [requestId, setRequestId] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [state, setState] = useState({ loading: true, equipment: [] });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api('/api/equipment/reservable-events', { signal: controller.signal, cache: 'no-store' }),
      api('/api/equipment-request-reviews', { signal: controller.signal, cache: 'no-store' }),
      api('/api/equipment/reservations', { signal: controller.signal, cache: 'no-store' }),
    ]).then(async ([eventData, requestData, reservationData]) => {
      const assigned = eventData.events || [];
      // Each assigned event's requests, read directly: the review queue alone
      // can come back empty. Its row is kept where it has one, for the linked
      // reservation; otherwise a reservation already made for the request
      // marks it as reserved, so it is not offered twice.
      const lists = await Promise.all(assigned.map(async event =>
        (await api(`/api/events/${encodeURIComponent(event.event_id)}/equipment-requests`, { signal: controller.signal, cache: 'no-store' })).equipment_requests || []));
      if (controller.signal.aborted) return;
      const queued = new Map((requestData.equipment_requests || []).map(row => [String(row.equipment_request_id), row]));
      const reserved = new Map((reservationData.reservations || []).filter(row => row.equipment_request_id != null)
        .map(row => [String(row.equipment_request_id), row]));
      setRequests(lists.flat().map(row => {
        const id = String(row.equipment_request_id);
        const merged = { ...row, ...queued.get(id) };
        return merged.linked_reservation || !reserved.has(id) ? merged : { ...merged, linked_reservation: reserved.get(id) };
      }));
      setEvents(assigned); setCatalogue(requestData.equipment); setState(s => ({ ...s, loading: false, error: '' }));
    }).catch(error => { if (!controller.signal.aborted) setState(s => ({ ...s, loading: false, error: error.message })); });
    return () => controller.abort();
  }, [api, refresh, reload]);
  useEffect(() => {
    if (!eventId) return;
    const controller = new AbortController();
    setState(s => ({ ...s, checking: true, equipment: [], error: '' }));
    api('/api/equipment/availability?event_id=' + encodeURIComponent(eventId), { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted) setState(s => ({ ...s, ...data, checking: false })); })
      .catch(error => { if (!controller.signal.aborted) setState(s => ({ ...s, checking: false, error: error.message })); });
    return () => controller.abort();
  }, [api, eventId, refresh, reload]);
  const pending = requests.filter(row => String(row.event_id) === eventId && row.status === 'pending' && !row.linked_reservation);
  const request = pending.find(row => String(row.equipment_request_id) === requestId);
  const matching = state.equipment.filter(row => {
    if (!request) return false;
    // Availability rows include the catalogue display name, while the review
    // queue's catalogue gives an exact type match without parsing model names.
    return catalogue.find(item => String(item.equipment_id) === String(row.equipment_id))?.equipment_type?.trim().toLowerCase() === request.equipment_type.trim().toLowerCase();
  });
  async function reserve(e) {
    e.preventDefault();
    if (busy || !request) return;
    if (Number(quantity) !== request.quantity) { setState(s => ({ ...s, error: 'Reserve the full requested quantity. Partial acceptance is not supported.' })); return; }
    setBusy(true); setMessage('');
    try {
      const result = await api(`/api/equipment-request-reviews/${requestId}/reservation`, { method: 'POST', body: { equipment_id: Number(equipmentId), quantity: Number(quantity) } });
      setMessage('Equipment reserved. The request is still pending. Return to Equipment Requests to accept it.');
      setRequestId(''); setEquipmentId(''); setQuantity(''); onReserved?.(result);
    } catch (error) { setState(s => ({ ...s, error: error.message })); }
    finally { setBusy(false); }
  }
  return <section className="panel">
    <h2>Reserve equipment</h2>
    <p>Select an event and its request, then reserve the full quantity. This holds equipment without accepting the request.</p>
    <button type="button" className="secondary" disabled={busy} onClick={() => setReload(value => value + 1)}>Refresh availability and requests</button>
    {state.loading && <p role="status">Loading assigned events and requests?</p>}
    <form onSubmit={reserve}><fieldset disabled={busy || state.loading}>
      <label>Event<select required value={eventId} onChange={e => { setEventId(e.target.value); setRequestId(''); setEquipmentId(''); setQuantity(''); setState(s => ({ ...s, equipment: [] })); }}>
        <option value="">Select an event</option>{events.map(row => <option key={row.event_id} value={row.event_id}>{row.event_name}</option>)}
      </select></label>
      <label>Equipment request<select required value={requestId} disabled={!eventId} onChange={e => {
        setRequestId(e.target.value); setEquipmentId('');
        setQuantity(String(pending.find(row => String(row.equipment_request_id) === e.target.value)?.quantity || ''));
      }}><option value="">Select a request</option>{pending.map(row => <option key={row.equipment_request_id} value={row.equipment_request_id}>#{row.equipment_request_id} ? {row.equipment_type} ? {row.quantity} units</option>)}</select></label>
      {eventId && !pending.length && <p>No pending requests without reservations for this event.</p>}
      {state.checking && <p role="status">Checking availability?</p>}
      <label>Equipment model<select required value={equipmentId} disabled={!request || state.checking} onChange={e => setEquipmentId(e.target.value)}>
        <option value="">Select equipment</option>{matching.map(row => <option key={row.equipment_id} value={row.equipment_id} disabled={row.available_quantity < request.quantity}>{row.name} ? {row.available_quantity} available</option>)}
      </select></label>
      <label>Quantity<input type="number" required min="1" step="1" value={quantity} onChange={e => setQuantity(e.target.value)} /></label>
      <button disabled={!can('equipment.reserve') || !request || !equipmentId || state.checking}>Reserve equipment</button>
    </fieldset></form>
    {state.error && <p role="alert" className="error">{state.error}</p>}
    {message && <p role="status">{message} <Link to="/equipment">Open Equipment Requests ?</Link></p>}
  </section>;
}
