import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useFeedback } from './FeedbackProvider';
import { eventRequestsApi } from '../services/eventRequests';

export default function EventRequestActions({ request, onChanged }) {
  const { api, can } = useAuth();
  const { confirm } = useFeedback();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const deletable = request.status === 'draft' && can('eventRequest.delete', request);
  const cancellable = ['submitted', 'rejected'].includes(request.status) && can('eventRequest.cancel', request);
  if (!deletable && !cancellable) return null;
  async function act(remove) {
    if (!(await confirm(`${remove ? 'Delete the draft' : 'Cancel'} "${request.event_name || 'Untitled request'}"? This cannot be undone.`, {
      title: remove ? 'Delete draft' : 'Cancel event request', confirmLabel: remove ? 'Delete draft' : 'Cancel request', destructive: true,
    }))) return;
    setBusy(true); setError('');
    try {
      const result = await eventRequestsApi(api, '/' + request.event_request_id + (remove ? '' : '/cancel'),
        remove ? { method: 'DELETE' } : { method: 'POST', body: {} });
      onChanged(request.event_request_id, remove ? null : result.event_request);
    } catch (err) { setError(err.message || 'Unable to update this request.'); }
    finally { setBusy(false); }
  }
  return <div className="event-request-card-actions">
    {cancellable && <button type="button" className="secondary" disabled={busy} onClick={() => act(false)}>Cancel request</button>}
    {deletable && <button type="button" className="secondary" disabled={busy} aria-label={`Delete draft ${request.event_name || 'Untitled request'}`} onClick={() => act(true)}>Delete draft</button>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}
