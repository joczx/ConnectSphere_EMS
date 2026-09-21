import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import EquipmentReservations from '../components/EquipmentReservations';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';

const formatDate = value => new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
}).format(new Date(value));

export default function Equipment() {
  const { api } = useAuth();
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState('');
  const [data, setData] = useState(null);
  const [equipmentId, setEquipmentId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [reservationsRefresh, setReservationsRefresh] = useState(0);

  const equipmentApi = useCallback((path, options = {}) => (
    api('/api/equipment' + path, { cache: 'no-store', ...options })
  ), [api]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setData(null);
    async function load() {
      try {
        const result = eventId
          ? await equipmentApi('/availability?event_id=' + encodeURIComponent(eventId), { signal: controller.signal })
          : await equipmentApi('/events', { signal: controller.signal });
        if (!controller.signal.aborted) {
          if (eventId) setData(result);
          else setEvents(result.events);
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [equipmentApi, eventId, refresh]);

  const selected = data?.equipment.find(item => String(item.equipment_id) === equipmentId);
  async function reserve(e) {
    e.preventDefault();
    if (saving) return;
    const amount = Number(quantity);
    if (!Number.isInteger(amount) || amount < 1) {
      setError('Quantity must be a positive whole number.');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await equipmentApi('/reservations', { method: 'POST', body: {
        event_id: eventId, equipment_id: equipmentId, quantity: amount,
      } });
      setMessage(`Reserved ${amount} × ${selected.name} for this event.`);
      setEquipmentId('');
      setQuantity('1');
      setReservationsRefresh(value => value + 1);
    } catch (err) {
      setError(err.message);
    }
    // Recheck after success or conflict without clearing the reservation error.
    try {
      setData(await equipmentApi('/availability?event_id=' + encodeURIComponent(eventId)));
    } catch {
      setData(null);
      setError(previous => previous || 'Unable to refresh availability. Use Refresh to try again.');
    } finally {
      setSaving(false);
    }
  }

  return <>
    <Navbar />
    <main className="container">
      <Link to="/home">← Home</Link>
      <div className="heading"><div><p className="eyebrow">EQUIPMENT</p><h1>Reserve equipment</h1></div>
        <button className="secondary" disabled={loading || saving} onClick={() => setRefresh(v => v + 1)}>Refresh</button></div>
      <p>Available to all signed-in users. Availability covers the full event duration. All times are in Singapore time (SGT).</p>
      <label>Event<select value={eventId} disabled={saving || (loading && !events.length)} onChange={e => {
        setEventId(e.target.value); setData(null); setEquipmentId(''); setMessage(''); setError('');
      }}><option value="">Select an event</option>{events.map(event =>
        <option key={event.event_id} value={event.event_id}>{event.event_name}</option>)}</select></label>
      {loading && <p role="status">Loading availability…</p>}
      {!loading && !events.length && !error && <p>No events found. Create an event before reserving equipment.</p>}
      {error && <p className="panel error" role="alert">{error}</p>}
      {message && <p className="panel" role="status">{message}</p>}
      {data && <>
        <p>{formatDate(data.starts_at)} – {formatDate(data.ends_at)}</p>
        <section className="panel">
          <h2>Equipment availability</h2>
          {!data.equipment.length ? <p>No equipment has been added to the catalogue yet.</p> : <>
            <div className="equipment-table"><table><thead><tr><th>Equipment</th><th>Total stock</th><th>Available</th><th>Reserved for this event</th></tr></thead>
              <tbody>{data.equipment.map(item => <tr key={item.equipment_id}><td>{item.name}</td><td>{item.total_quantity}</td><td>{item.available_quantity}</td><td>{item.reserved_quantity}</td></tr>)}</tbody>
            </table></div>
            <p>Availability accounts for other reservations during this event, including this event’s existing reservations. Stock can be reused when events do not overlap.</p>
            <form onSubmit={reserve}>
              <label>Equipment<select required value={equipmentId} disabled={saving} onChange={e => { setEquipmentId(e.target.value); setQuantity('1'); }}>
                <option value="">Select equipment</option>{data.equipment.map(item => <option key={item.equipment_id} value={item.equipment_id} disabled={item.available_quantity < 1 || item.reserved_quantity > 0}>
                  {item.name} — {item.reserved_quantity ? 'Already reserved' : `${item.available_quantity} available`}</option>)}
              </select></label>
              <label>Quantity<input type="number" required min="1" max={selected?.available_quantity || 1} step="1" value={quantity} disabled={saving || !selected} onChange={e => setQuantity(e.target.value)} /></label>
              <button disabled={saving || !selected || selected.reserved_quantity > 0 || selected.available_quantity < 1}>{saving ? 'Reserving…' : 'Confirm reservation'}</button>
            </form>
          </>}
        </section>
      </>}
      <EquipmentReservations refresh={reservationsRefresh}
        onChanged={() => setRefresh(value => value + 1)} />
    </main>
  </>;
}
