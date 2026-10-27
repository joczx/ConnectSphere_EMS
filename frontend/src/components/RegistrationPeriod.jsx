import { useState } from 'react';
import { DateTime } from 'luxon';
import { useAuth } from '../auth/AuthContext';

const inputTime = value => value ? DateTime.fromISO(value).setZone('Asia/Singapore').toFormat("yyyy-MM-dd'T'HH:mm") : '';
export const registrationDate = value => value ? DateTime.fromISO(value).setZone('Asia/Singapore').toFormat('dd LLL yyyy, HH:mm') + ' SGT' : 'Not set';

export default function RegistrationPeriod({ event, onSaved }) {
  const { api, can } = useAuth();
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const editable = can('event.registrationPeriod', event)
    && ['planning', 'pending_safety_checks', 'confirmed'].includes(event.status)
    && (!event.end_datetime || Date.now() < Date.parse(event.end_datetime))
    && (!event.registration_closes_at || Date.now() < Date.parse(event.registration_closes_at));
  async function save(e) {
    e.preventDefault();
    setError(''); setMessage('');
    const opens = DateTime.fromISO(form.opens, { zone: 'Asia/Singapore' });
    const closes = DateTime.fromISO(form.closes, { zone: 'Asia/Singapore' });
    if (!opens.isValid || !closes.isValid || closes.toMillis() <= opens.toMillis()) {
      setError('Registration must close after it opens.'); return;
    }
    setBusy(true);
    try {
      const result = await api(`/api/events/${event.event_id}/registration-period`, { method: 'PATCH', body: {
        registration_opens_at: opens.toUTC().toISO(), registration_closes_at: closes.toUTC().toISO(),
        waiting_list_enabled: form.waiting,
      } });
      onSaved(result.event); setForm(null); setMessage('Registration settings saved.');
    } catch (err) { setError(err.message || 'Unable to save registration settings.'); }
    finally { setBusy(false); }
  }
  return <section className="panel event-detail-section">
    <h2>Registration period</h2>
    <dl className="detail-grid">
      <div><dt>Opens</dt><dd>{registrationDate(event.registration_opens_at)}</dd></div>
      <div><dt>Closes</dt><dd>{registrationDate(event.registration_closes_at)}</dd></div>
      <div><dt>Waiting list</dt><dd>{event.waiting_list_enabled ? 'Enabled when capacity is reached' : 'Disabled'}</dd></div>
    </dl>
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {editable && !form && <button type="button" className="secondary" onClick={() => {
      setError(''); setMessage(''); setForm({ opens: inputTime(event.registration_opens_at), closes: inputTime(event.registration_closes_at), waiting: !!event.waiting_list_enabled });
    }}>Set or update registration</button>}
    {form && <form onSubmit={save}>
      <p>All times are in Singapore time (SGT). Settings can change before or during registration.</p>
      <fieldset disabled={busy}>
        <label>Registration opens<input required type="datetime-local" value={form.opens} onChange={e => setForm({ ...form, opens: e.target.value })} /></label>
        <label>Registration closes<input required type="datetime-local" value={form.closes} onChange={e => setForm({ ...form, closes: e.target.value })} /></label>
        <label><input type="checkbox" checked={form.waiting} onChange={e => setForm({ ...form, waiting: e.target.checked })} />Enable a waiting list when capacity is reached</label>
        <button type="submit">{busy ? 'Saving…' : 'Save registration settings'}</button>
        <button type="button" className="secondary" onClick={() => { setForm(null); setError(''); }}>Cancel</button>
      </fieldset>
    </form>}
  </section>;
}
