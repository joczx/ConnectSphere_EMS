import { useEffect, useState } from 'react';
import { readApiResponse } from '../services/http';

const date = value => new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
}).format(new Date(value));

export default function EquipmentReservations({ token, refresh, onChanged }) {
  const [rows, setRows] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [confirmId, setConfirmId] = useState(null);
  const [reload, setReload] = useState(0);

  async function api(path = '', options = {}) {
    return readApiResponse(await fetch('/api/equipment/reservations' + path, {
      ...options, cache: 'no-store',
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
    }));
  }

  function showRows(result) {
    setRows(result.reservations);
    setQuantities(Object.fromEntries(result.reservations.map(row => [row.reservation_id, String(row.quantity)])));
  }

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setConfirmId(null);
    api('', { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) showRows(result);
    }).catch(err => {
      if (!controller.signal.aborted) { setRows([]); setError(err.message); }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [token, refresh, reload]);

  async function change(row, cancel = false) {
    if (busy) return;
    const quantity = Number(quantities[row.reservation_id]);
    if (!cancel && (!Number.isInteger(quantity) || quantity < 1)) {
      setError('Quantity must be a positive whole number.');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    let changed = false;
    try {
      await api('/' + row.reservation_id, {
        method: cancel ? 'DELETE' : 'PATCH',
        ...(!cancel && { body: JSON.stringify({ quantity }) }),
      });
      changed = true;
      setConfirmId(null);
      setMessage(cancel ? `Cancelled ${row.name} for ${row.event_name}.` : `Updated ${row.name} to ${quantity} for ${row.event_name}.`);
    } catch (err) {
      setError(err.message);
    }
    // Refresh after conflicts as well as success, preserving the mutation error.
    try { showRows(await api()); }
    catch (err) { setRows([]); setError(previous => previous || err.message); }
    finally { setBusy(false); }
    if (changed) onChanged();
  }

  return <section className="panel" aria-labelledby="my-reservations-heading">
    <div className="heading">
      <h2 id="my-reservations-heading">My equipment reservations</h2>
      <button type="button" className="secondary" disabled={loading || busy} onClick={() => setReload(value => value + 1)}>Refresh reservations</button>
    </div>
    <p>Manage reservations you created. Reducing or cancelling a reservation releases stock for its event period.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {loading ? <p role="status">Loading your reservations…</p> : <>
      {!rows.length && !error && <p>You have no equipment reservations.</p>}
      {rows.map(row => <article key={row.reservation_id} className="panel">
        <h3>{row.name} — {row.event_name}</h3>
        <p>{date(row.starts_at)} – {date(row.ends_at)} (SGT)</p>
        <p>Reserved: {row.quantity}. Maximum currently available for this reservation: {row.maximum_quantity}.</p>
        <form onSubmit={event => { event.preventDefault(); change(row); }}>
          <label>Quantity for {row.name}
            <input type="number" min="1" step="1" required
              max={Math.max(row.quantity, row.maximum_quantity)}
              value={quantities[row.reservation_id] ?? row.quantity} disabled={busy}
              onChange={event => setQuantities(values => ({ ...values, [row.reservation_id]: event.target.value }))} />
          </label>
          <button disabled={busy || Number(quantities[row.reservation_id]) === row.quantity}>Save quantity</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setConfirmId(row.reservation_id)}>Cancel reservation</button>
        </form>
        {confirmId === row.reservation_id && <div>
          <p>Cancel all {row.quantity} units of {row.name} for {row.event_name}?</p>
          <button type="button" disabled={busy} onClick={() => change(row, true)}>Confirm cancellation</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setConfirmId(null)}>Keep reservation</button>
        </div>}
      </article>)}
    </>}
  </section>;
}
