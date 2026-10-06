import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import { useAuth } from '../auth/AuthContext';
import {
  FACILITIES, LAYOUTS,
  display, label, toInput, toIso, toItems, toLines,
} from '../services/eventFields';

function date(value) {
  return value ? new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(value)) : 'Not specified';
}
function Detail({ label: text, value }) {
  return <div><dt>{text}</dt><dd style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{value === null || value === undefined || value === '' ? 'Not specified' : value}</dd></div>;
}

// The event as the edit form holds it. Built from the saved row, so cancelling
// is just a matter of building it again.
const formFrom = (event) => ({
  event_name: event.event_name ?? '',
  purpose: event.purpose ?? '',
  description: event.description ?? '',
  registration_needs: event.registration_needs ?? '',
  start_datetime: toInput(event.start_datetime),
  end_datetime: toInput(event.end_datetime),
  capacity_needed: event.capacity_needed ?? '',
  room_layout: event.room_layout ?? '',
  required_facilities: event.required_facilities ?? [],
  need_wheelchair_accessibility: !!event.need_wheelchair_accessibility,
  need_blind_accessibility: !!event.need_blind_accessibility,
  equipment_requirements: toLines(event.equipment_requirements),
});

// Only what the user actually changed is sent, so an untouched field is never
// rewritten and never shows up in the Activity History.
function changedFields(event, form) {
  const next = {
    event_name: form.event_name.trim(),
    purpose: form.purpose.trim(),
    description: form.description.trim(),
    registration_needs: form.registration_needs.trim() || null,
    start_datetime: toIso(form.start_datetime),
    end_datetime: toIso(form.end_datetime),
    capacity_needed: form.capacity_needed === '' ? null : Number(form.capacity_needed),
    room_layout: form.room_layout || null,
    required_facilities: form.required_facilities,
    need_wheelchair_accessibility: form.need_wheelchair_accessibility,
    need_blind_accessibility: form.need_blind_accessibility,
    equipment_requirements: toItems(form.equipment_requirements),
  };
  const body = {};
  for (const [field, value] of Object.entries(next)) {
    if (JSON.stringify(value) !== JSON.stringify(saved(event, field))) body[field] = value;
  }
  return body;
}

// The saved value in the same shape the form produces, so comparing the two
// does not report a change that is only a difference of representation.
function saved(event, field) {
  if (field.endsWith('_datetime')) return event[field] ? new Date(event[field]).toISOString() : null;
  if (field === 'equipment_requirements') return toItems(toLines(event[field]));
  if (field === 'required_facilities') return event[field] ?? [];
  if (field.startsWith('need_')) return !!event[field];
  if (field === 'capacity_needed') return event[field] ?? null;
  if (field === 'registration_needs') return event[field] ?? null;
  return event[field] ?? '';
}

export default function Events() {
  const { api } = useAuth();
  const { eventId } = useParams();
  const [state, setState] = useState({ loading: true });
  const [refresh, setRefresh] = useState(0);
  const [form, setForm] = useState({
    equipment_type: '',
    quantity: 1,
    technical_requirements: '',
  });
  const [submitState, setSubmitState] = useState({ message: '', error: '' });
  const [userNames, setUserNames] = useState({});
  const [coordinatorChoices, setCoordinatorChoices] = useState([]);
  const [reassignForm, setReassignForm] = useState({ open: false, value: '', busy: false, error: '', message: '' });
  const [edit, setEdit] = useState({ open: false, values: null, busy: false, error: '', details: null, message: '' });
  const [warning, setWarning] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setState((current) => ({ ...current, loading: true, error: null }));
      try {
        const path = '/api/events' + (eventId ? '/' + encodeURIComponent(eventId) : '');
        const data = await api(path, { cache: 'no-store', signal: controller.signal });
        if (!controller.signal.aborted) setState((current) => ({ ...current, data, key: eventId, loading: false, error: null }));
      } catch (err) {
        if (!controller.signal.aborted) setState((current) => ({ ...current, loading: false, error: err.message || 'Unable to load event information.' }));
      }
    }
    load();
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, eventId, refresh]);

  useEffect(() => {
    if (!eventId) return;
    let ignore = false;
    async function loadEquipment() {
      try {
        const data = await api(`/api/events/${encodeURIComponent(eventId)}/equipment-requests`, { cache: 'no-store' });
        if (!ignore) setState((current) => ({ ...current, equipment: data.equipment_requests || [], equipmentError: null }));
      } catch (err) {
        if (!ignore) setState((current) => ({ ...current, equipmentError: err.message || 'Unable to load equipment requests.' }));
      }
    }
    loadEquipment();
    return () => { ignore = true; };
  }, [api, eventId, refresh]);

  useEffect(() => {
    if (!eventId) return;
    let ignore = false;
    api(`/api/events/${encodeURIComponent(eventId)}/activity`, { cache: 'no-store' })
      .then(data => { if (!ignore) setState(current => ({ ...current, activity: data.activity || [], activityError: null })); })
      // Not an empty history: swallowing this would render "no changes have
      // been recorded" over a Critical Edit the viewer simply could not read.
      .catch(err => { if (!ignore) setState(current => ({ ...current, activity: null, activityError: err.message || 'Unable to load the activity history.' })); });
    return () => { ignore = true; };
  }, [api, eventId, refresh]);

  const [equipmentTypes, setEquipmentTypes] = useState([]);

  useEffect(() => {
    let ignore = false;
    api('/api/equipment-types', { cache: 'no-store' })
      .then(data => { if (!ignore) setEquipmentTypes(data.equipment_types || []); })
      .catch(err => { if (!ignore) setSubmitState({ message: '', error: err.message }); });
    return () => { ignore = true; };
  }, [api]);

  async function submitEquipmentRequest(event) {
    event.preventDefault();
    setSubmitState({ message: '', error: '' });

    try {
      const data = await api(`/api/events/${encodeURIComponent(eventId)}/equipment-requests`, {
        method: 'POST',
        body: {
          equipment_type: form.equipment_type,
          quantity: Number(form.quantity),
          technical_requirements: form.technical_requirements,
        },
      });
      setSubmitState({ message: data.message || 'Equipment request submitted successfully.', error: '' });
      setForm({ equipment_type: '', quantity: 1, technical_requirements: '' });
      setRefresh(value => value + 1);
    } catch (err) {
      setSubmitState({ message: '', error: err.message || 'Unable to submit equipment request.' });
    }
  }

  const data = state.key === eventId ? state.data : null;
  const event = data?.event;
  const equipmentRequests = state.equipment || [];
  const activity = state.activity || [];
  const editable = event?.status === 'planning';

  useEffect(() => {
    if (!event) return;

    const ids = [
      event.event_organiser_id,
      event.event_coordinator_id,
      event.technical_support_id,
      event.venue_staff_id,
    ].filter(Boolean).join(',');

    if (ids) {
      api(`/api/users?ids=${encodeURIComponent(ids)}`, { cache: 'no-store' })
        .then((data) => setUserNames(data.users || {}))
        .catch(() => setUserNames({}));
    } else {
      setUserNames({});
    }

    api('/api/users?role=event_coordinator', { cache: 'no-store' })
      .then((data) => {
        const options = Object.entries(data.users || {}).map(([id, name]) => ({ id, name }));
        setCoordinatorChoices(options.filter(({ id }) => id !== event.event_coordinator_id));
      })
      .catch(() => setCoordinatorChoices([]));
  }, [api, event]);

  async function reassignCoordinator(eventSubmit) {
    eventSubmit.preventDefault();
    if (!event || !reassignForm.value) return;

    setReassignForm((current) => ({ ...current, busy: true, error: '', message: '' }));
    try {
      const data = await api(`/api/events/${encodeURIComponent(eventId)}/coordinator`, {
        method: 'PATCH',
        body: { event_coordinator_id: reassignForm.value },
      });
      setReassignForm({ open: false, value: '', busy: false, error: '', message: data.message || 'Coordinator reassigned.' });
      setRefresh(value => value + 1);
    } catch (err) {
      setReassignForm((current) => ({ ...current, busy: false, error: err.message || 'Unable to reassign the coordinator.' }));
    }
  }

  function startEditing() {
    setEdit({ open: true, values: formFrom(event), busy: false, error: '', details: null, message: '' });
    setWarning(null);
  }

  // "The system discards all pending edits and status if the user clicks
  // Cancel" - from the warning modal and from the form alike.
  function discardEdits() {
    setEdit({ open: false, values: null, busy: false, error: '', details: null, message: '' });
    setWarning(null);
  }

  const setField = (name, value) => setEdit(current => ({ ...current, values: { ...current.values, [name]: value } }));

  async function save(body, confirmCritical) {
    setEdit(current => ({ ...current, busy: true, error: '', details: null }));
    try {
      const result = await api(`/api/events/${encodeURIComponent(eventId)}`, {
        method: 'PATCH',
        body: confirmCritical ? { ...body, confirm_critical: true } : body,
      });
      setWarning(null);
      setEdit({ open: false, values: null, busy: false, error: '', details: null, message: result.message || 'Event information updated.' });
      setRefresh(value => value + 1);
    } catch (err) {
      // The server refuses a critical change until it is confirmed, and names
      // the fields so the warning can list them.
      if (err.data?.critical_fields) {
        setWarning({ fields: err.data.critical_fields, body });
        setEdit(current => ({ ...current, busy: false }));
        return;
      }
      setEdit(current => ({ ...current, busy: false, error: err.message || 'Unable to save these changes.', details: err.details }));
    }
  }

  function submitEdit(submitEvent) {
    submitEvent.preventDefault();
    const body = changedFields(event, edit.values);
    if (!Object.keys(body).length) {
      setEdit(current => ({ ...current, error: 'Nothing has been changed yet.' }));
      return;
    }
    save(body, false);
  }

  return <>
    <Navbar />
    <main className="container">
      {eventId && <Link to="/events">← My events</Link>}
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{eventId ? 'Event information' : 'My events'}</h1></div>
        <button className="secondary" onClick={() => setRefresh(value => value + 1)} disabled={state.loading}>Refresh</button></div>
      <p>All times are in Singapore time (SGT). Information refreshes every minute and when you return to this window.</p>
      {state.loading && <p role="status">Loading latest information…</p>}
      {state.error && <div role="alert" className="panel error">{state.error} Use Refresh to try again.</div>}
      {data?.events && <section className="event-list" aria-label="Your events">
        {data.events.length === 0 && <div className="panel">No events are available to you yet. Contact your event organiser or coordinator to arrange access.</div>}
        {data.events.map(item => <Link className="panel event-link" key={item.event_id} to={'/events/' + item.event_id}><h2>{item.event_name}</h2><p>{date(item.start_datetime)}</p><p className="metadata">Status: {item.status ? item.status.charAt(0).toUpperCase() + item.status.slice(1) : 'Not specified'}</p><span>View event information →</span></Link>)}
      </section>}

      {event && <article className="panel">
        <div className="heading" style={{ alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>{event.event_name}</h2>
          <div>
            {editable && !edit.open && <button type="button" onClick={startEditing}>Edit event information</button>}{' '}
            <button type="button" className="secondary" onClick={() => setReassignForm(current => ({ ...current, open: !current.open, value: '', error: '', message: '' }))}>Reassign Event Coordinator</button>
          </div>
        </div>
        {edit.message && <div className="success" style={{ marginBottom: '12px' }} role="status">{edit.message}</div>}
        {!editable && <p className="metadata">This event is {event.status}. Details can only be changed during planning.</p>}
        {reassignForm.message && <div className="success" style={{ marginBottom: '12px' }}>{reassignForm.message}</div>}
        {reassignForm.error && <div className="error" style={{ marginBottom: '12px' }}>{reassignForm.error}</div>}
        {reassignForm.open && <form onSubmit={reassignCoordinator} style={{ display: 'grid', gap: '12px', marginBottom: '20px' }}>
          <label>
            Replacement event coordinator
            <select value={reassignForm.value} onChange={(e) => setReassignForm((current) => ({ ...current, value: e.target.value }))} required>
              <option value="">Select an event coordinator</option>
              {coordinatorChoices.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}
            </select>
          </label>
          <button type="submit" disabled={reassignForm.busy}>{reassignForm.busy ? 'Reassigning…' : 'Save reassignment'}</button>
        </form>}

        {!edit.open && <dl>
          <Detail label="Status" value={event.status ? event.status.charAt(0).toUpperCase() + event.status.slice(1) : null} />
          <Detail label="Purpose" value={event.purpose} />
          <Detail label="Description" value={event.description} />
          <Detail label="Start date and time" value={date(event.start_datetime)} />
          <Detail label="End date and time" value={date(event.end_datetime)} />
          <Detail label="Expected attendance" value={event.capacity_needed} />
          <Detail label="Room layout" value={event.room_layout ? label(event.room_layout) : null} />
          <Detail label="Required facilities" value={display('required_facilities', event.required_facilities)} />
          <Detail label="Wheelchair accessibility needed" value={event.need_wheelchair_accessibility ? 'Yes' : 'No'} />
          <Detail label="Accessibility for blind attendees needed" value={event.need_blind_accessibility ? 'Yes' : 'No'} />
          <Detail label="Equipment requirements" value={display('equipment_requirements', event.equipment_requirements)} />
          <Detail label="Registration needs" value={event.registration_needs} />
          <Detail label="Event organiser" value={userNames[event.event_organiser_id] || (event.event_organiser_id ? event.event_organiser_id.slice(0, 8) : 'Not specified')} />
          <Detail label="Event coordinator" value={userNames[event.event_coordinator_id] || (event.event_coordinator_id ? event.event_coordinator_id.slice(0, 8) : 'Not specified')} />
          <Detail label="Technical support" value={userNames[event.technical_support_id] || (event.technical_support_id ? event.technical_support_id.slice(0, 8) : 'Not specified')} />
          <Detail label="Venue staff" value={userNames[event.venue_staff_id] || (event.venue_staff_id ? event.venue_staff_id.slice(0, 8) : 'Not specified')} />
        </dl>}

        {edit.open && <form onSubmit={submitEdit} style={{ display: 'grid', gap: '12px' }}>
          <p className="metadata">Changes to the proposed dates, expected attendance, venue requirements, accessibility needs or equipment requirements may affect arrangements already made. You will be asked to confirm those before they are saved.</p>
          {edit.error && <div role="alert" className="error">{edit.error}
            {edit.details && <ul>{Object.values(edit.details).map(message => <li key={message}>{message}</li>)}</ul>}</div>}
          <fieldset disabled={edit.busy} style={{ display: 'grid', gap: '12px', border: 0, padding: 0 }}>
            <label>Event name<input value={edit.values.event_name} onChange={e => setField('event_name', e.target.value)} required /></label>
            <label>Purpose<input value={edit.values.purpose} onChange={e => setField('purpose', e.target.value)} required /></label>
            <label>Description<textarea rows="4" value={edit.values.description} onChange={e => setField('description', e.target.value)} required /></label>
            <label>Registration needs<textarea rows="3" value={edit.values.registration_needs} onChange={e => setField('registration_needs', e.target.value)} /></label>
            <label>Start date and time<input type="datetime-local" value={edit.values.start_datetime} onChange={e => setField('start_datetime', e.target.value)} required /></label>
            <label>End date and time<input type="datetime-local" value={edit.values.end_datetime} onChange={e => setField('end_datetime', e.target.value)} required /></label>
            <label>Expected attendance<input type="number" min="1" value={edit.values.capacity_needed} onChange={e => setField('capacity_needed', e.target.value)} required /></label>
            <label>Room layout<select value={edit.values.room_layout} onChange={e => setField('room_layout', e.target.value)} required>
              <option value="">Select a layout</option>{LAYOUTS.map(layout => <option key={layout} value={layout}>{label(layout)}</option>)}
            </select></label>
            <label>Required facilities (hold Ctrl or ⌘ to select several)
              <select multiple value={edit.values.required_facilities} onChange={e => setField('required_facilities', Array.from(e.target.selectedOptions, option => option.value))}>
                {FACILITIES.map(facility => <option key={facility} value={facility}>{label(facility)}</option>)}
              </select></label>
            {[['need_wheelchair_accessibility', 'Wheelchair accessibility needed'], ['need_blind_accessibility', 'Accessibility for blind attendees needed']].map(([name, text]) =>
              <label key={name}>{text}<select value={edit.values[name] ? 'yes' : 'no'} onChange={e => setField(name, e.target.value === 'yes')}><option value="no">No</option><option value="yes">Yes</option></select></label>)}
            <label>Equipment requirements (one per line: type, quantity, notes — or write "none")
              <textarea rows="3" placeholder="projector, 2, HDMI input" value={edit.values.equipment_requirements} onChange={e => setField('equipment_requirements', e.target.value)} /></label>
          </fieldset>
          <div className="heading">
            <button type="button" className="secondary" onClick={discardEdits} disabled={edit.busy}>Cancel</button>
            <button type="submit" disabled={edit.busy}>{edit.busy ? 'Saving…' : 'Save changes'}</button>
          </div>
        </form>}
      </article>}

      {warning && <div role="alertdialog" aria-modal="true" aria-labelledby="critical-heading" className="panel" style={{ border: '2px solid currentColor', marginTop: '16px' }}>
        <h2 id="critical-heading">Confirm changes to existing arrangements</h2>
        <p>You have changed information that other arrangements may already depend on:</p>
        <ul>{warning.fields.map(field => <li key={field}>{field}</li>)}</ul>
        <p>Venue bookings and equipment reservations made for this event may no longer be suitable. Please review the impact before saving. This will be recorded as a Critical Edit in the Activity History.</p>
        <div className="heading">
          <button type="button" className="secondary" onClick={discardEdits} disabled={edit.busy}>Cancel</button>
          <button type="button" onClick={() => save(warning.body, true)} disabled={edit.busy}>{edit.busy ? 'Saving…' : 'Confirm and save'}</button>
        </div>
      </div>}

      {eventId && <section className="panel" style={{ marginTop: '24px' }}>
        <h2>Equipment requests</h2>
        {state.equipmentError && <div className="error">{state.equipmentError}</div>}
        {submitState.error && <div className="error">{submitState.error}</div>}
        {submitState.message && <div className="success">{submitState.message}</div>}

        <form onSubmit={submitEquipmentRequest} style={{ display: 'grid', gap: '12px', marginTop: '16px' }}>
          <label>
            Equipment Type
            <select value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} required>
              <option value="">Select</option>
              {equipmentTypes.map(type => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <label>
            Quantity
            <input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required />
          </label>
          <label>
            Technical requirements
            <textarea value={form.technical_requirements} onChange={(e) => setForm({ ...form, technical_requirements: e.target.value })} rows="6" />
          </label>
          <button type="submit">Submit equipment request</button>
        </form>

        <div style={{ marginTop: '24px' }}>
          {equipmentRequests.length === 0 ? (
            <p>No equipment requests for this event yet.</p>
          ) : (
            equipmentRequests.map((item) => (
              <div key={item.equipment_request_id || item.id} className="panel" style={{ marginTop: '12px' }}>
                <h3>{item.equipment_type}</h3>
                <EquipmentRequestStatus request={item} />
                <p>Technical requirements: {item.technical_requirements || 'Not specified'}</p>
              </div>
            ))
          )}
        </div>
      </section>}

      {eventId && <section className="panel" style={{ marginTop: '24px' }}>
        <h2>Activity history</h2>
        {state.activityError && <div role="alert" className="error">{state.activityError} Use Refresh to try again.</div>}
        {!state.activityError && activity.length === 0 ? <p>No changes have been recorded for this event yet.</p> : activity.length > 0 && <dl>
          {activity.map(entry => <div key={entry.activity_id}>
            <dt>{entry.change_type === 'critical_edit' ? 'Critical Edit' : 'Edit'} — {date(entry.created_at)}</dt>
            <dd>
              {userNames[entry.changed_by] || (entry.changed_by ? entry.changed_by.slice(0, 8) : 'Unknown user')}
              <ul>{Object.entries(entry.changes || {}).map(([field, change]) => <li key={field}>
                {label(field)}: {display(field, change.from)} → {display(field, change.to)}
              </li>)}</ul>
            </dd>
          </div>)}
        </dl>}
      </section>}
    </main>
  </>;
}
