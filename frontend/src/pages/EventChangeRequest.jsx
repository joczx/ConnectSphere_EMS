import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import RequiredIndicator from '../components/RequiredIndicator';
import { useAuth } from '../auth/AuthContext';
import { useFeedback } from '../components/FeedbackProvider';
import { FACILITIES, LAYOUTS, label } from '../services/eventFields';
import { changedValues, formFromEvent, importanceLabel, statusLabel, submissionBody } from '../services/eventChangeRequests';

const REASON_ERROR = 'Please provide a reason for this change request';

const FIELD_LABELS = {
  event_name: 'Event name', description: 'Description', start_datetime: 'Start date and time',
  end_datetime: 'End date and time', capacity_needed: 'Expected attendance', room_layout: 'Room layout',
  required_facilities: 'Venue requirements', need_wheelchair_accessibility: 'Wheelchair accessibility',
  need_blind_accessibility: 'Accessibility for blind attendees', equipment_requirements: 'Equipment requirements',
};

export default function EventChangeRequest() {
  const { api } = useAuth();
  const { confirm, notify } = useFeedback();
  const [searchParams] = useSearchParams();
  const [state, setState] = useState({ loading: true, events: [], requests: [], error: '', historyError: '' });
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      api('/api/event-change-requests/eligible-events', { cache: 'no-store', signal: controller.signal }),
      api('/api/event-change-requests/mine', { cache: 'no-store', signal: controller.signal }),
    ]).then(([eventResult, requestResult]) => {
      if (controller.signal.aborted) return;
      if (eventResult.status === 'rejected') {
        setState({ loading: false, events: [], requests: [], error: eventResult.reason.message, historyError: '' });
        return;
      }
      const eventData = eventResult.value;
      const events = eventData.events || [];
      const requests = requestResult.status === 'fulfilled' ? requestResult.value.change_requests || [] : [];
      const historyError = requestResult.status === 'rejected'
        ? requestResult.reason.message || 'Unable to load your previous change requests.'
        : '';
      setState({ loading: false, events, requests, error: '', historyError });
      const requested = searchParams.get('event_id');
      const initial = events.find(event => String(event.event_id) === requested);
      if (initial) {
        setSelected(initial);
        setForm(formFromEvent(initial));
      }
    }).catch(error => { if (!controller.signal.aborted) setState({ loading: false, events: [], requests: [], error: error.message, historyError: '' }); });
    return () => controller.abort();
  }, [api, searchParams]);

  function chooseEvent(eventId) {
    const event = state.events.find(item => String(item.event_id) === eventId) || null;
    setSelected(event);
    setForm(event ? formFromEvent(event) : null);
    setErrors({});
    setResult(null);
  }

  function setField(name, value) {
    setForm(current => ({ ...current, [name]: value }));
    setErrors(current => ({ ...current, [name]: undefined, proposed_values: undefined }));
  }

  function discardEdits() {
    setForm(selected ? formFromEvent(selected) : null);
    setErrors({});
    notify('Your pending event changes have been discarded.', 'info');
  }

  async function submit(confirmCritical = false) {
    setBusy(true);
    setErrors({});
    try {
      const data = await api(`/api/events/${encodeURIComponent(selected.event_id)}/change-requests`, {
        method: 'POST',
        body: submissionBody(selected, form, confirmCritical),
        successFeedback: false,
      });
      setResult(data.change_request);
      setForm(null);
      setState(current => ({
        ...current,
        events: current.events.filter(event => event.event_id !== selected.event_id),
        requests: [{ ...data.change_request, event_name: selected.event_name }, ...current.requests],
      }));
      notify(data.message || 'Event change request submitted successfully.');
    } catch (error) {
      if (error.data?.critical_fields) {
        setBusy(false);
        const accepted = await confirm(
          `You changed ${error.data.critical_fields.join(', ')}. These changes may affect existing arrangements. Review their impact before submitting.`,
          { title: 'Confirm critical changes', confirmLabel: 'Confirm and submit', cancelLabel: 'Cancel' },
        );
        if (accepted) await submit(true);
        else discardEdits();
        return;
      }
      setErrors({ ...(error.details || {}), _form: error.message || 'Unable to submit this change request.' });
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = {};
    if (!form.reason.trim()) nextErrors.reason = REASON_ERROR;
    if (!Object.keys(changedValues(selected, form)).length) {
      nextErrors.proposed_values = 'Make at least one change before submitting.';
    }
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }
    submit(false);
  }

  return <>
    <Navbar />
    <main className="container">
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>Submit event change request</h1></div></div>
      <p>Propose changes to an event you submitted. Critical changes require coordinator approval; name or description-only requests are applied automatically.</p>
      {state.loading && <p role="status">Loading your events…</p>}
      {state.error && <div className="panel error" role="alert">{state.error}</div>}
      {!state.loading && !state.error && state.events.length === 0 && !result && <div className="panel">You have no events currently eligible for a change request.</div>}

      {!state.error && <label className="panel">Event<RequiredIndicator />
        <select value={selected?.event_id || ''} onChange={event => chooseEvent(event.target.value)} disabled={busy || !!result}>
          <option value="">Select one of your events</option>
          {state.events.map(event => <option key={event.event_id} value={event.event_id}>{event.event_name} — {statusLabel(event.status)}</option>)}
        </select>
      </label>}

      {result && <section className="panel venue-success" role="status">
        <h2>Change request submitted</h2>
        <p>Status: <strong>{statusLabel(result.status)}</strong></p>
        {result.importance && <p>Type: <strong>{importanceLabel(result.importance)}</strong></p>}
        <p>Request reference: {result.event_change_request_id}</p>
      </section>}

      {selected && form && <form className="panel" onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
        <h2>{selected.event_name}</h2>
        <p className="metadata">Current event status: {statusLabel(selected.status)}</p>
        {errors._form && <div role="alert" className="error">{errors._form}</div>}
        {errors.proposed_values && <div role="alert" className="error">{errors.proposed_values}</div>}
        <fieldset disabled={busy} style={{ display: 'grid', gap: '12px', border: 0, padding: 0 }}>
          <label>Event name<RequiredIndicator /><input value={form.event_name} onChange={event => setField('event_name', event.target.value)} required /></label>
          <label>Description<RequiredIndicator /><textarea rows="3" value={form.description} onChange={event => setField('description', event.target.value)} required /></label>
          <label>Start date and time<RequiredIndicator /><input type="datetime-local" value={form.start_datetime} onChange={event => setField('start_datetime', event.target.value)} required /></label>
          <label>End date and time<RequiredIndicator /><input type="datetime-local" value={form.end_datetime} onChange={event => setField('end_datetime', event.target.value)} required /></label>
          <label>Expected attendance<RequiredIndicator /><input type="number" min="1" value={form.capacity_needed} onChange={event => setField('capacity_needed', event.target.value)} required /></label>
          <label>Room layout<RequiredIndicator /><select value={form.room_layout} onChange={event => setField('room_layout', event.target.value)} required>
            <option value="">Select a layout</option>{LAYOUTS.map(layout => <option key={layout} value={layout}>{label(layout)}</option>)}
          </select></label>
          <label>Required facilities (hold Ctrl or ⌘ to select several)
            <select multiple value={form.required_facilities} onChange={event => setField('required_facilities', Array.from(event.target.selectedOptions, option => option.value))}>
              {FACILITIES.map(facility => <option key={facility} value={facility}>{label(facility)}</option>)}
            </select>
          </label>
          {[['need_wheelchair_accessibility', 'Wheelchair accessibility needed'], ['need_blind_accessibility', 'Accessibility for blind attendees needed']].map(([name, text]) =>
            <label key={name}>{text}<select value={form[name] ? 'yes' : 'no'} onChange={event => setField(name, event.target.value === 'yes')}><option value="no">No</option><option value="yes">Yes</option></select></label>)}
          <label>Equipment requirements (one per line: type, quantity, notes — or write “none”)<RequiredIndicator />
            <textarea rows="3" value={form.equipment_requirements} onChange={event => setField('equipment_requirements', event.target.value)} required />
          </label>
          <label>Reason for this change request<RequiredIndicator />
            <textarea rows="4" maxLength="2000" value={form.reason} onChange={event => setField('reason', event.target.value)} aria-invalid={!!errors.reason} aria-describedby={errors.reason ? 'change-reason-error' : undefined} required />
          </label>
          {errors.reason && <p id="change-reason-error" role="alert" className="error">{errors.reason}</p>}
        </fieldset>
        <div className="heading">
          <button type="button" className="secondary" onClick={discardEdits} disabled={busy}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? 'Submitting…' : 'Submit change request'}</button>
        </div>
      </form>}

      {!state.loading && !state.error && <section className="change-request-list">
        <h2>Your change requests</h2>
        {state.requests.length === 0 && <p className="panel">No change requests</p>}
        {state.requests.length > 0 && <div className="event-list">{state.requests.map(request => (
          <article className="panel change-request-card" key={request.event_change_request_id}>
            <div className="change-request-tags">
              <span className={`change-request-tag change-request-${request.importance}`}>{importanceLabel(request.importance)}</span>
              <span className={`change-request-tag change-request-${request.status}`}>{statusLabel(request.status)}</span>
            </div>
            <h3>{request.event_name}</h3>
            <p><strong>Reason:</strong> {request.reason}</p>
            <p className="metadata">Changed: {(request.changed_fields || Object.keys(request.changes || {})).map(field => FIELD_LABELS[field] || field).join(', ')}</p>
            {request.decision_reason && <p><strong>Decision reason:</strong> {request.decision_reason}</p>}
            <p className="metadata">Submitted {new Date(request.submitted_at).toLocaleString()}</p>
          </article>
        ))}</div>}
      </section>}
    </main>
  </>;
}

