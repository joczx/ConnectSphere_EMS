import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';

export default function WithdrawRegistration({ eventId, startDatetime, status, disabled = false, onWithdrawn }) {
  const { api } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!['registered', 'waiting_list'].includes(status)) return null;
  const beforeStart = Date.now() < Date.parse(startDatetime);
  async function withdraw() {
    setBusy(true); setError('');
    try {
      const result = await api(`/api/events/${eventId}/registrations/withdraw`, { method: 'POST', body: {} });
      onWithdrawn(result);
    } catch (err) {
      setError(err.message || 'Unable to withdraw your registration.');
    } finally { setBusy(false); }
  }
  return <>
    <button type="button" className="secondary" disabled={disabled || busy || !beforeStart} onClick={withdraw}>
      {busy ? 'Withdrawing…' : 'Withdraw registration'}
    </button>
    {!beforeStart && <p>Registration cannot be withdrawn at or after the event start time.</p>}
    {error && <p role="alert" className="error">{error}</p>}
  </>;
}
