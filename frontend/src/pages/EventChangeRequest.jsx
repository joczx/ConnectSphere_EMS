import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import RequiredIndicator from '../components/RequiredIndicator';
import EventFormSection from '../components/EventFormSection';
import RequiredFacilitiesPicker from '../components/RequiredFacilitiesPicker';
import EquipmentRequirementsPicker from '../components/EquipmentRequirementsPicker';
import { registrationDate } from '../components/RegistrationPeriod';
import { useAuth } from '../auth/AuthContext';
import { useFeedback } from '../components/FeedbackProvider';
import { LAYOUTS, label, toItems, toLines } from '../services/eventFields';
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
  const [pickerRevision, setPickerRevision] = useState(0);

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
    setPickerRevision(value => value + 1);
    setForm(selected ? formFromEvent(selected) : null);
    setErrors({});
    notify('Your pending event changes have been discarded.', 'info');
  }

  async function submit(confirmCritical = false, proposedForm = form) {
    setBusy(true);
    setErrors({});
    try {
      const data = await api(`/api/events/${encodeURIComponent(selected.event_id)}/change-requests`, {
        method: 'POST',
        body: submissionBody(selected, proposedForm, confirmCritical),
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
        if (accepted) await submit(true, proposedForm);
        else discardEdits();
        return;
      }
      // The shared API helper already displays submission failures in the toast.
      setErrors(error.details || {});
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const facilities = data.getAll('required_facilities');
    const proposedForm = { ...form,
      required_facilities: facilities.includes('none') ? [] : facilities,
      equipment_requirements: toLines(JSON.parse(data.get('equipment_requirements') || 'null')),
    };
    const nextErrors = {};
    if (!form.reason.trim()) nextErrors.reason = REASON_ERROR;
    if (!Object.keys(changedValues(selected, proposedForm)).length) {
      nextErrors.proposed_values = 'Make at least one change before submitting.';
    }
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      notify(nextErrors.reason || nextErrors.proposed_values, 'error', 'Check your information');
      return;
    }
    submit(false, proposedForm);
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

      {selected && form && <form className="panel event-form" onSubmit={handleSubmit}>
        <h2>{selected.event_name}</h2>
        <p className="metadata">Current event status: {statusLabel(selected.status)}</p>
        <fieldset disabled={busy}>
          <p className="metadata">Update the sections below and explain your changes before submitting.</p>
          <EventFormSection title="1. Event details" description="Update your event name and description.">
          <label>Event name<RequiredIndicator /><input value={form.event_name} onChange={event => setField('event_name', event.target.value)} required /></label>
          <label>Description<RequiredIndicator /><textarea rows="3" value={form.description} onChange={event => setField('description', event.target.value)} required /></label>
          </EventFormSection>
          <EventFormSection title="2. Schedule and attendance" description="Enter the event dates and the number of people expected.">
          <label>Start date and time<RequiredIndicator /><input type="datetime-local" value={form.start_datetime} onChange={event => setField('start_datetime', event.target.value)} required /></label>
          <label>End date and time<RequiredIndicator /><input type="datetime-local" value={form.end_datetime} onChange={event => setField('end_datetime', event.target.value)} required /></label>
          <label>Expected attendance<RequiredIndicator /><input type="number" min="1" value={form.capacity_needed} onChange={event => setField('capacity_needed', event.target.value)} required /></label>
          </EventFormSection>
          <EventFormSection title="3. Venue and accessibility" description="Tell us what the space needs to provide.">
          <label>Room layout<RequiredIndicator /><select value={form.room_layout} onChange={event => setField('room_layout', event.target.value)} required>
            <option value="">Select a layout</option>{LAYOUTS.map(layout => <option key={layout} value={layout}>{label(layout)}</option>)}
          </select></label>
          <RequiredFacilitiesPicker key={`facilities-${selected.event_id}-${pickerRevision}`} initialItems={form.required_facilities} />
          {[['need_wheelchair_accessibility', 'Wheelchair accessibility needed'], ['need_blind_accessibility', 'Accessibility for blind attendees needed']].map(([name, text]) =>
            <label key={name}>{text}<select value={form[name] ? 'yes' : 'no'} onChange={event => setField(name, event.target.value === 'yes')}><option value="no">No</option><option value="yes">Yes</option></select></label>)}
          </EventFormSection>
          <EventFormSection title="4. Equipment requirements" description="Update the equipment required for your event.">
          <EquipmentRequirementsPicker key={`equipment-${selected.event_id}-${pickerRevision}`} initialItems={toItems(form.equipment_requirements)} />
          </EventFormSection>
          <EventFormSection title="5. Reason for change" description="Explain why these changes are needed so the coordinator can review them.">
          <label>Reason for this change request<RequiredIndicator />
            <textarea rows="4" maxLength="2000" value={form.reason} onChange={event => setField('reason', event.target.value)} aria-invalid={!!errors.reason} aria-describedby={errors.reason ? 'change-reason-error' : undefined} required />
          </label>
          {errors.reason && <p id="change-reason-error" role="alert" className="error">{errors.reason}</p>}
          </EventFormSection>
        </fieldset>
        <div className="heading event-form-actions">
          <button type="button" className="secondary" onClick={discardEdits} disabled={busy}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? 'Submitting…' : 'Submit change request'}</button>
        </div>
      </form>}

      {!state.loading && !state.error && <section className="panel change-request-list organiser-change-history" aria-labelledby="change-history-heading">
        <div className="change-history-heading"><div><h2 id="change-history-heading">Your change requests</h2>
          <p className="metadata">Submitted changes and feedback</p></div>
          {!state.historyError && <span className="change-history-count">{state.requests.length} {state.requests.length === 1 ? 'request' : 'requests'}</span>}
        </div>
        {state.historyError && <p className="panel error" role="alert">{state.historyError}</p>}
        {!state.historyError && state.requests.length === 0 && <div className="panel change-history-empty"><h3>No change requests yet</h3><p>Select an event above to submit your first change request.</p></div>}
        {state.requests.length > 0 && <div className="change-history-rows">{state.requests.map(request => (
          <article className="panel change-history-card" key={request.event_change_request_id}>
            <header className="change-history-card-heading"><div>
              <p className="eyebrow">REQUEST #{request.event_change_request_id}</p>
              <h3>{request.event_name || 'Event change request'}</h3>
              <p className="metadata">Submitted {registrationDate(request.submitted_at)}</p>
            </div><div className="change-request-tags">
              <span className={`change-request-tag change-request-${request.importance}`}>{importanceLabel(request.importance)}</span>
              <span className={`change-request-tag change-request-${request.status}`}>{statusLabel(request.status)}</span>
            </div></header>
            <dl className="change-history-details">
              <div><dt>Reason for change</dt><dd>{request.reason}</dd></div>
              <div><dt>Requested changes</dt><dd className="change-history-fields">{(request.changed_fields || Object.keys(request.changes || {})).map(field => <span key={field}>{FIELD_LABELS[field] || label(field)}</span>)}</dd></div>
            </dl>
            {request.decision_reason && <div className="change-history-feedback"><h4>Coordinator feedback</h4><p>{request.decision_reason}</p></div>}
          </article>
        ))}</div>}
      </section>}
    </main>
  </>;
}

