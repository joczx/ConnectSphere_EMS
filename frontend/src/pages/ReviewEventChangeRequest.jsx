import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { useFeedback } from '../components/FeedbackProvider';
import { display, label } from '../services/eventFields';
import { importanceLabel, reviewApi, statusLabel } from '../services/eventChangeRequests';

const FIELD_LABELS = {
  event_name: 'Event name', description: 'Description', start_datetime: 'Start date and time',
  end_datetime: 'End date and time', capacity_needed: 'Expected attendance', room_layout: 'Room layout',
  required_facilities: 'Venue requirements', need_wheelchair_accessibility: 'Wheelchair accessibility',
  need_blind_accessibility: 'Accessibility for blind attendees', equipment_requirements: 'Equipment requirements',
};

const IMPACT_LABELS = {
  venue_availability: 'Recheck venue availability for the proposed date and time.',
  equipment_reservations: 'Recheck existing equipment reservations.',
  event_schedule: 'Recheck the event schedule and timing.',
  venue_capacity: 'Recheck that the venue capacity fits the expected attendance.',
  venue_suitability: 'Recheck that the venue still meets the event requirements.',
  accessibility_arrangements: 'Recheck accessibility arrangements with the venue.',
  equipment_availability: 'Recheck equipment availability and technical requirements.',
};

export default function ReviewEventChangeRequest() {
  const { api } = useAuth();
  const { requestId } = useParams();
  const { confirm, notify } = useFeedback();
  const [state, setState] = useState({ loading: true });
  const [reason, setReason] = useState('');
  const [attempt, setAttempt] = useState({ busy: false, error: '', reasonError: '' });

  const load = useCallback(() => {
    const controller = new AbortController();
    setState({ loading: true });
    reviewApi(api, `/${encodeURIComponent(requestId)}`, { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted) setState({ data }); })
      .catch(error => { if (!controller.signal.aborted) setState({ error: error.message || 'Unable to load this change request.' }); });
    return controller;
  }, [api, requestId]);

  useEffect(() => {
    const controller = load();
    return () => controller.abort();
  }, [load]);

  async function decide(decision) {
    if (decision === 'reject' && !reason.trim()) {
      setAttempt({ busy: false, error: '', reasonError: 'Please provide a reason for rejecting this change request.' });
      return;
    }
    const impacts = state.data?.preparation_impacts || [];
    const approvalMessage = impacts.length
      ? `Approve and apply this request? You will need to reconsider: ${impacts.map(item => IMPACT_LABELS[item] || label(item)).join(' ')}`
      : 'Approve and apply this change request?';
    const accepted = await confirm(
      decision === 'approve' ? approvalMessage : 'Reject this change request? The event will remain unchanged.',
      { title: decision === 'approve' ? 'Confirm critical changes' : 'Confirm rejection', confirmLabel: decision === 'approve' ? 'Approve and apply' : 'Reject request', destructive: decision === 'reject' },
    );
    if (!accepted) return;

    setAttempt({ busy: true, error: '', reasonError: '' });
    try {
      const result = await reviewApi(api, `/${encodeURIComponent(requestId)}/decision`, {
        method: 'POST', body: { decision, reason: reason.trim() }, successFeedback: false,
      });
      notify(result.message);
      setReason('');
      setAttempt({ busy: false, error: '', reasonError: '' });
      load();
    } catch (error) {
      setAttempt({ busy: false, error: error.message || 'Unable to save this decision.', reasonError: error.details?.reason || '' });
    }
  }

  const request = state.data?.change_request;
  const impacts = state.data?.preparation_impacts || [];
  const pendingImportant = request?.status === 'pending_review' && request?.importance === 'important';

  return <>
    <Navbar />
    <main className="container">
      <Link to="/review-event-change-requests">← Review event change requests</Link>
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{request?.event_name || 'Event change request'}</h1></div></div>
      {state.loading && <p role="status">Loading change request…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {request && <>
        <section className="panel change-request-summary">
          <div className="change-request-tags">
            <span className={`change-request-tag change-request-${request.importance}`}>{importanceLabel(request.importance)}</span>
            <span className={`change-request-tag change-request-${request.status}`}>{statusLabel(request.status)}</span>
          </div>
          <h2>Reason for request</h2><p>{request.reason}</p>
          {request.decision_reason && <><h2>Decision reason</h2><p>{request.decision_reason}</p></>}
        </section>

        <section className="panel change-request-comparison">
          <h2>Requested changes</h2>
          <div className="change-request-diffs">{Object.entries(request.changes || {}).map(([field, change]) => (
            <article key={field} className="change-request-diff">
              <h3>{FIELD_LABELS[field] || label(field)}</h3>
              <dl><dt>Current</dt><dd>{display(field, change.from)}</dd><dt>Proposed</dt><dd>{display(field, change.to)}</dd></dl>
            </article>
          ))}</div>
        </section>

        {request.importance === 'non_important' && <section className="panel venue-success">
          <h2>Non-critical change</h2><p>This request did not require coordinator approval and was applied automatically.</p>
        </section>}

        {impacts.length > 0 && <section className="panel change-request-impacts">
          <h2>Preparations to reconsider</h2>
          <p>Review these arrangements before approving the request:</p>
          <ul>{impacts.map(item => <li key={item}>{IMPACT_LABELS[item] || label(item)}</li>)}</ul>
        </section>}

        {pendingImportant && <form className="panel change-request-decision" onSubmit={event => event.preventDefault()}>
          <h2>Decision</h2>
          {attempt.error && <p className="error" role="alert">{attempt.error}</p>}
          <fieldset disabled={attempt.busy}>
            <label>Reason for decision <span className="metadata">(required when rejecting)</span>
              <textarea rows="4" maxLength="2000" value={reason} onChange={event => { setReason(event.target.value); setAttempt(current => ({ ...current, reasonError: '' })); }} aria-invalid={!!attempt.reasonError} aria-describedby={attempt.reasonError ? 'decision-reason-error' : undefined} />
            </label>
            {attempt.reasonError && <p id="decision-reason-error" className="error" role="alert">{attempt.reasonError}</p>}
            <div className="change-request-actions">
              <button type="button" className="secondary" onClick={() => decide('reject')}>Reject</button>
              <button type="button" onClick={() => decide('approve')}>{attempt.busy ? 'Saving…' : 'Approve'}</button>
            </div>
          </fieldset>
        </form>}
      </>}
    </main>
  </>;
}

