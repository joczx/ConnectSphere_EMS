import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function ReserveEquipment({ onReserved }) {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [state, setState] = useState({ loadingEvents: true, equipment: [] });
  const [refresh, setRefresh] = useState(0);
  const saving = useRef(false);
  const generation = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    api('/api/equipment/reservable-events', { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted) { setEvents(data.events); setState(s => ({ ...s, loadingEvents: false })); } })
      .catch(err => { if (!controller.signal.aborted) setState(s => ({ ...s, loadingEvents: false, error: err.message })); });
    return () => controller.abort();
  }, [api]);

  useEffect(() => {
    if (!eventId) return;
    const controller = new AbortController();
    const current = ++generation.current;
    setState(s => ({ ...s, loading: true, equipment: [] }));
    api('/api/equipment/availability?event_id=' + encodeURIComponent(eventId), { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted && generation.current === current) setState(s => ({ ...s, ...data, loading: false })); })
      .catch(err => { if (!controller.signal.aborted && generation.current === current) setState(s => ({ ...s, loading: false, error: err.message })); });
    return () => controller.abort();
  }, [api, eventId, refresh]);

  const item = state.equipment.find(row => String(row.equipment_id) === equipmentId);
  async function reserve(e) {
    e.preventDefault();
    if (saving.current) return;
    const amount = Number(quantity);
    if (!item || !Number.isInteger(amount) || amount < 1) {
      setState(s => ({ ...s, error: 'Select equipment and enter a positive whole quantity.' }));
      return;
    }
    if (amount > item.available_quantity) {
      setState(s => ({ ...s, error: `Only ${item.available_quantity} available for this event.` }));
      return;
    }
    saving.current = true;
    setState(s => ({ ...s, busy: true, error: '', message: '' }));
    try {
      const data = await api('/api/equipment/reservations', { method: 'POST', body: {
        event_id: eventId, equipment_id: equipmentId, quantity: amount,
      } });
      setState(s => ({ ...s, message: data.message || 'Equipment reserved successfully.' }));
      onReserved?.(data);
    } catch (err) {
      setState(s => ({ ...s, error: err.message || 'Unable to reserve equipment.' }));
    } finally {
      saving.current = false;
      setState(s => ({ ...s, busy: false }));
      setRefresh(value => value + 1);
    }
  }

  return <section className="panel" aria-labelledby="reserve-heading">
    <h2 id="reserve-heading">Reserve available equipment</h2>
    <p>Select an event assigned to you. Availability uses the event dates and existing overlapping reservations.</p>
    <Link to="/equipment-availability">Check equipment availability for other dates</Link>
    {state.loadingEvents && <p role="status">Loading assigned events...</p>}
    {!state.loadingEvents && !events.length && !state.error && <p>No events are assigned to you for technical support.</p>}
    <form onSubmit={reserve}>
      <fieldset disabled={state.busy || state.loadingEvents}>
        <label>Event to reserve for<select required value={eventId} onChange={e => {
          ++generation.current;
          setEventId(e.target.value); setEquipmentId('');
          setState(s => ({ ...s, equipment: [], starts_at: null, ends_at: null, error: '', message: '', loading: !!e.target.value }));
        }}><option value="">Select an event</option>{events.map(event => <option key={event.event_id} value={event.event_id}>{event.event_name}</option>)}</select></label>
        {state.loading && <p role="status">Checking availability...</p>}
        {state.starts_at && eventId && <p>Event period: {new Date(state.starts_at).toLocaleString()} to {new Date(state.ends_at).toLocaleString()}</p>}
        <label>Equipment model<select required disabled={!eventId || state.loading} value={equipmentId} onChange={e => setEquipmentId(e.target.value)}>
          <option value="">Select equipment</option>{state.equipment.map(row => <option key={row.equipment_id} value={row.equipment_id} disabled={row.available_quantity < 1 || row.standalone_reserved}>
            {row.name} — {row.available_quantity} available{row.standalone_reserved ? ' (already reserved)' : ''}
          </option>)}
        </select></label>
        {item && <p>Available quantity: {item.available_quantity}. Reserved for this event: {item.reserved_quantity}.</p>}
        <label>Quantity to reserve<input type="number" required min="1" step="1" max={item?.available_quantity || undefined} value={quantity} onChange={e => setQuantity(e.target.value)} /></label>
        <button disabled={!item || state.loading || item.available_quantity < 1 || item.standalone_reserved}>{state.busy ? 'Reserving...' : 'Confirm reservation'}</button>
        <button type="button" className="secondary" disabled={!eventId || state.loading} onClick={() => { setState(s => ({ ...s, error: '', message: '' })); setRefresh(v => v + 1); }}>Refresh availability</button>
      </fieldset>
    </form>
    {state.error && <p role="alert" className="error">{state.error}</p>}
    {state.message && <p role="status">{state.message}</p>}
  </section>;
}
