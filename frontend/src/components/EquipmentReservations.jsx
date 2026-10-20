import RequiredIndicator from './RequiredIndicator';
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useFeedback } from './FeedbackProvider';

const date = value => new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
}).format(new Date(value));

export default function EquipmentReservations({ refresh, onChanged, eventId = '' }) {
  const { notify, confirm } = useFeedback();
  const { api, can } = useAuth();
  const [rows, setRows] = useState([]);
  const [quantity, setQuantity] = useState('');
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [reload, setReload] = useState(0);

  const reservationsApi = useCallback((path = '', options = {}) => (
    api('/api/equipment/reservations' + path, { cache: 'no-store', ...options })
  ), [api]);

  useEffect(() => {
    setEditing(null);
    setError('');
    setMessage('');
  }, [eventId]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setEditing(null);
    reservationsApi('', { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) setRows(result.reservations);
    }).catch(err => {
      if (!controller.signal.aborted) { setRows([]); setError(err.message); }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [reservationsApi, refresh, reload]);

  async function change(row, cancel = false) {
    if (busy) return;
    if (cancel && !(await confirm(`Cancel all ${row.quantity} units of ${row.name} for ${row.event_name}?`,
      { title: 'Cancel equipment reservation', confirmLabel: 'Cancel reservation', destructive: true }))) return;
    const amount = Number(quantity);
    if (!cancel && (!Number.isInteger(amount) || amount < 1 || amount > 2147483647)) {
      notify('Quantity must be a positive whole number.', 'error', 'Check reservation quantity');
      setError('Quantity must be a positive whole number.');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await reservationsApi('/' + row.reservation_id, {
        method: cancel ? 'DELETE' : 'PATCH',
        ...(!cancel && { body: { quantity: amount } }),
      });
      setEditing(null);
      setMessage(cancel ? `Cancelled ${row.name} for ${row.event_name}.` : `Updated ${row.name} to ${amount} for ${row.event_name}.`);
      onChanged?.(result);
    } catch (err) {
      setError(err.message);
    }
    // Refresh stock conflicts and successful changes without erasing feedback.
    try { setRows((await reservationsApi()).reservations); }
    catch (err) { setRows([]); setError(previous => previous || err.message); }
    finally { setBusy(false); }
  }

  const visibleRows = rows.filter(row => !eventId || String(row.event_id) === String(eventId));
  return <section className="panel" aria-labelledby="my-reservations-heading" style={{ marginTop: '24px' }}>
    <div className="heading">
      <h2 id="my-reservations-heading">My equipment reservations</h2>
      <button type="button" className="secondary" disabled={loading || busy} onClick={() => setReload(value => value + 1)}>Refresh reservations</button>
    </div>
    <p>Edit or cancel reservations you created. Changes are also shown on the event page.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {loading ? <p role="status">Loading your reservations...</p> : <>
      {!visibleRows.length && !error && <p>{eventId ? 'You have no reservations for this event.' : 'You have no equipment reservations.'}</p>}
      {visibleRows.map(row => <article key={row.reservation_id} className="panel">
        <h3>{row.name} ? {row.event_name}</h3>
        <p>{date(row.starts_at)} ? {date(row.ends_at)} (SGT)</p>
        <p>Reserved quantity: {row.quantity}</p>
        {editing === row.reservation_id ? <form onSubmit={event => { event.preventDefault(); change(row); }}>
          <label>Quantity for {row.name}
            <RequiredIndicator /><input autoFocus type="number" min="1" max="2147483647" step="1" required
              value={quantity} disabled={busy} onChange={event => setQuantity(event.target.value)} />
          </label>
          <button disabled={busy || Number(quantity) === row.quantity}>{busy ? 'Saving...' : 'Save changes'}</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => { setEditing(null); notify('Reservation editing cancelled. No changes were saved.', 'info'); }}>Cancel editing</button>
        </form> : can('equipment.manageReservation') && <button type="button" className="secondary" disabled={busy} onClick={() => {
          setEditing(row.reservation_id); setQuantity(String(row.quantity)); setError(''); setMessage('');
        }}>Edit quantity</button>}
        {can('equipment.manageReservation') && <button type="button" className="secondary" disabled={busy} onClick={() => change(row, true)}>Cancel reservation</button>}
      </article>)}
    </>}
  </section>;
}
