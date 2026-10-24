import EventList from '../components/EventList';
import RegistrationPeriod from '../components/RegistrationPeriod';
import EventFormSection from '../components/EventFormSection';
import RequiredIndicator from '../components/RequiredIndicator';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useFeedback } from '../components/FeedbackProvider';
import EquipmentRequestStatus from '../components/EquipmentRequestStatus';
import EquipmentRequestForm from '../components/EquipmentRequestForm';
import { useAuth } from '../auth/AuthContext';
import { loadEvents } from '../services/eventLoading';
import { statusLabel } from '../services/venueBookings';
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
  const { confirm, notify } = useFeedback();
  const { api, can, canAccess, canViewEvent, userId } = useAuth();
  const { eventId } = useParams();
  const [state, setState] = useState({ loading: true });
  const [refresh, setRefresh] = useState(0);
  const manualRefresh = useRef(false);
  const [userNames, setUserNames] = useState({});
  const [edit, setEdit] = useState({ open: false, values: null, busy: false, error: '', details: null, message: '' });
  const [lifecycle, setLifecycle] = useState({ busy: false, error: '', message: '' });
  // `allowed`: whether this viewer takes part in venue booking at all.
  // `canRequest`: whether they may request one (coordinators, not staff).
  const [venue, setVenue] = useState({ assigned: null, bookings: [], error: '', allowed: true, canRequest: false });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const showFeedback = manualRefresh.current;
      manualRefresh.current = false;
      setState((current) => ({ ...current, loading: true, error: null }));
      try {
        const path = '/api/events' + (eventId ? '/' + encodeURIComponent(eventId) : '');
        const { data, statusWarning } = await loadEvents(api, path, { cache: 'no-store', signal: controller.signal,
          feedback: showFeedback, successMessage: 'Event information refreshed.' });
        if (!controller.signal.aborted) setState((current) => ({ ...current, data, key: eventId, loading: false, error: null, statusWarning }));
      } catch (err) {
        if (showFeedback && !controller.signal.aborted) notify(err.message || 'Unable to refresh event information.', 'error');
        if (!controller.signal.aborted) setState((current) => ({ ...current, loading: false, error: err.message || 'Unable to load event information.' }));
      }
    }
    load();
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, eventId, refresh, notify]);

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

  // The venue side of planning this event: what has been requested for it so
  // far, so the coordinator does not request a second venue without knowing.
  useEffect(() => {
    if (!eventId) return undefined;
    let ignore = false;
    // This event's bookings, for everyone the event names: its Organiser,
    // Coordinator, Technical Support, Venue Staff and Safety Officer (045).
    // Whether a coordinator may request a venue is decided by
    // can('event.findVenue') where the button is shown.
    api(`/api/venue-bookings/events/${encodeURIComponent(eventId)}`, { cache: 'no-store' })
      .then(data => {
        if (!ignore) setVenue(current => ({ ...current, bookings: data.bookings || [], error: '', allowed: true, canRequest: true }));
      })
      .catch(err => {
        if (ignore) return;
        // Not assigned to the event: no booking list.
        if (err.status === 403 || err.status === 404) {
          setVenue(current => ({ ...current, allowed: false, error: '' }));
          return;
        }
        // Until 045 is run the endpoint is unavailable. Fall back to the full
        // list, which serves Event Coordinators and Venue Staff only.
        api('/api/venue-bookings', { cache: 'no-store' })
          .then(data => {
            if (ignore) return;
            const forThisEvent = (data.bookings || [])
              .filter(booking => String(booking.event_id) === String(eventId));
            setVenue(current => ({ ...current, bookings: forThisEvent, error: '', allowed: true, canRequest: !!data.can_submit }));
          })
          .catch(fallback => {
            if (ignore) return;
            if (fallback.status === 403) setVenue(current => ({ ...current, allowed: false, error: '' }));
            else setVenue(current => ({ ...current, error: fallback.message || 'Unable to load venue booking requests.' }));
          });
      });
    return () => { ignore = true; };
  }, [api, eventId, refresh]);

  const data = state.key === eventId ? state.data : null;
  // Only events the viewer is assigned to; a Coordinator Lead sees them all.
  const hiddenEvent = !!data?.event && !canViewEvent(data.event);
  const event = hiddenEvent ? null : data?.event;
  const equipmentRequests = state.equipment || [];
  const activity = state.activity || [];
  const editable = event?.status === 'planning';
  // The event's Organiser, Technical Support Staff and Safety Officer cannot
  // list venue bookings, but still see which venue the event has.
  const venueReadOnly = !!event && !venue.allowed && !!userId
    && [event.event_organiser_id, event.technical_support_id, event.safety_officer_id].includes(userId);
  // Who sees which button: ACTIONS in auth/access.js. The status rules stay here.
  const canRequestChange = !!event && can('changeRequest.create', event)
    && ['planning', 'pending_safety_checks', 'confirmed'].includes(event.status);
  const canCancel = !!event && ['planning', 'confirmed'].includes(event.status) && can('event.cancel', event);

  async function updateLifecycle(action, ready) {
    if (action === 'cancel' && !(await confirm('Cancel this event? This cannot be undone.', { title: 'Cancel event', confirmLabel: 'Cancel event', destructive: true }))) return;
    setLifecycle({ busy: true, error: '', message: '' });
    try {
      const result = await api(`/api/events/${encodeURIComponent(eventId)}/${action}`, {
        method: action === 'cancel' ? 'POST' : 'PATCH',
        body: action === 'cancel' ? {} : { ready },
      });
      setState(current => ({ ...current, data: { ...current.data, event: result.event } }));
      setLifecycle({ busy: false, error: '', message: action === 'cancel'
        ? 'Event cancelled.' : `Registration readiness saved. Event status: ${label(result.event.status)}.` });
      setRefresh(value => value + 1);
    } catch (error) {
      setLifecycle({ busy: false, error: error.message || 'Unable to update the event.', message: '' });
    }
  }
  const approvedVenues = venue.bookings
    .filter(booking => booking.status === 'approved')
    .map(booking => booking.venue_name);
  // Bookings arrive newest first. The assigned Venue Staff is taken to the
  // newest one still awaiting a decision, or else the newest one.
  const bookingToReview = venue.bookings.find(booking => booking.status === 'submitted') || venue.bookings[0];

  useEffect(() => {
    if (!event) return;

    const ids = [
      event.event_organiser_id,
      event.event_coordinator_id,
      event.technical_support_id,
      event.venue_staff_id,
      event.safety_officer_id,
    ].filter(Boolean).join(',');

    if (ids) {
      api(`/api/users?ids=${encodeURIComponent(ids)}`, { cache: 'no-store' })
        .then((data) => setUserNames(data.users || {}))
        .catch(() => setUserNames({}));
    } else {
      setUserNames({});
    }
  }, [api, event]);

  useEffect(() => {
    if (!event?.venue_id) {
      setVenue(current => ({ ...current, assigned: null }));
      return undefined;
    }
    let ignore = false;
    api(`/api/venues/${encodeURIComponent(event.venue_id)}`, { cache: 'no-store' })
      .then(data => { if (!ignore) setVenue(current => ({ ...current, assigned: data.venue })); })
      // The venue name is a convenience. Failing to read it must not make the
      // rest of the planning page look broken.
      .catch(() => { if (!ignore) setVenue(current => ({ ...current, assigned: null })); });
    return () => { ignore = true; };
  }, [api, event?.venue_id]);

  function startEditing() {
    // The version being edited. Sent back on save so the server can refuse
    // rather than overwrite if someone else has saved in the meantime.
    setEdit({ open: true, values: formFrom(event), base: event.updated_at, busy: false, error: '', details: null, message: '' });
  }

  // "The system discards all pending edits and status if the user clicks
  // Cancel" - from the warning modal and from the form alike.
  function discardEdits() {
    notify('Your unsaved event changes have been discarded.', 'info');
    setEdit({ open: false, values: null, busy: false, error: '', details: null, message: '' });
  }

  const setField = (name, value) => setEdit(current => ({ ...current, values: { ...current.values, [name]: value } }));

  async function save(body, confirmCritical) {
    setEdit(current => ({ ...current, busy: true, error: '', details: null }));
    try {
      const result = await api(`/api/events/${encodeURIComponent(eventId)}`, {
        method: 'PATCH',
        body: { ...body, expected_updated_at: edit.base, ...(confirmCritical ? { confirm_critical: true } : {}) },
      });
      setEdit({ open: false, values: null, busy: false, error: '', details: null, message: result.message || 'Event information updated.' });
      setRefresh(value => value + 1);
    } catch (err) {
      // The server refuses a critical change until it is confirmed, and names
      // the fields so the warning can list them.
      if (err.data?.critical_fields) {
        setEdit(current => ({ ...current, busy: false }));
        const accepted = await confirm(`You changed ${err.data.critical_fields.join(', ')}. These changes may affect existing venue bookings and equipment reservations and will be recorded as a Critical Edit. Review the arrangements after saving.`,
          { title: 'Confirm changes to existing arrangements', confirmLabel: 'Confirm and save', cancelLabel: 'Discard changes' });
        if (accepted) await save(body, true);
        else discardEdits();
        return;
      }
      // Someone else saved first. Their version is loaded so it can be read
      // before deciding what to do; the edits are kept in the form meanwhile.
      if (err.data?.stale) {
        setEdit(current => ({ ...current, busy: false, error: err.message, details: null }));
        setRefresh(value => value + 1);
        return;
      }
      setEdit(current => ({ ...current, busy: false, error: err.message || 'Unable to save these changes.', details: err.details }));
    }
  }

  function submitEdit(submitEvent) {
    submitEvent.preventDefault();
    const body = changedFields(event, edit.values);
    if (!Object.keys(body).length) {
      notify('Nothing has been changed yet.', 'info');
      setEdit(current => ({ ...current, error: 'Nothing has been changed yet.' }));
      return;
    }
    save(body, false);
  }

  return <>
    <Navbar />
    <main className={eventId ? "container event-reference-detail" : "container event-reference-workspace"}>
      {eventId && <Link to="/events">← My events</Link>}
      <div className="heading"><div><p className="eyebrow">EVENT WORKSPACE</p><h1>{eventId ? event?.event_name || 'Event information' : 'Events'}</h1></div>
        <div className="event-reference-actions">
          {event && editable && can('event.edit', event) && !edit.open && <button type="button" onClick={startEditing}>Edit event</button>}
          {event && canRequestChange && !edit.open && <Link className="button-link secondary" to={`/event-change-requests/new?event_id=${encodeURIComponent(event.event_id)}`}>Request changes</Link>}
          {event && canCancel && <button type="button" className="secondary event-cancel-action" disabled={lifecycle.busy} onClick={() => updateLifecycle('cancel')}>Cancel event</button>}
          {!eventId && can('event.create') && <Link className="button-link" to="/event-requests/new">+ New event</Link>}
          <button className="secondary" onClick={() => { manualRefresh.current = true; setRefresh(value => value + 1); }} disabled={state.loading}>Refresh</button></div></div>
      {!eventId && <p className="event-page-description">Track schedules, arrangements and progress in one place.</p>}
      <p className="metadata event-refresh-note">Singapore time (SGT) - Refreshes every minute and when you return to this window.</p>
      {state.loading && <p role="status">Loading latest information…</p>}
      {state.error && <div role="alert" className="panel error">{state.error} Use Refresh to try again.</div>}
      {state.statusWarning && <p role="status" className="panel">{state.statusWarning}</p>}
      {hiddenEvent && <div role="alert" className="panel error">Event not found or access unavailable.</div>}
      {data?.events && <EventList events={data.events.filter(canViewEvent)} />}
      {event && <>
        <div className="event-reference-identity"><span className={'event-stage event-stage-' + event.status}>{label(event.status)}</span><span>Event #{event.event_id}</span></div>
        <div className="event-reference-info-cards">
          {[['Starts', date(event.start_datetime)], ['Ends', date(event.end_datetime)], ['Attendance', event.capacity_needed ?? '-'], ['Purpose', event.purpose || '-']].map(([name, value]) => <div key={name}><span>{name}</span><strong>{value}</strong></div>)}
        </div>
      </>}

      {event && <div className="event-reference-columns"><div className="event-reference-main">
      <RegistrationPeriod key={event.event_id} event={event} onSaved={updated => {
        setState(current => ({ ...current, data: { ...current.data, event: updated } }));
        setRefresh(value => value + 1);
      }} />
      {event && <article className="panel event-detail-section" id="event-overview" tabIndex={-1}>
        <div className="heading" style={{ alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Event details</h2>

        </div>
        {edit.message && <div className="success" style={{ marginBottom: '12px' }} role="status">{edit.message}</div>}
        {lifecycle.error && <p role="alert" className="error">{lifecycle.error}</p>}
        {lifecycle.message && <p role="status" className="success">{lifecycle.message}</p>}
        {!editable && !canRequestChange && <p className="metadata">This event is {event.status}. Details can only be changed during planning.</p>}

        {!edit.open && <><h3>About this event</h3><dl className="event-detail-grid">
          <Detail label="Status" value={event.status ? event.status.charAt(0).toUpperCase() + event.status.slice(1) : null} />
          <Detail label="Purpose" value={event.purpose} />
          <Detail label="Description" value={event.description} />
        </dl><h3>Venue and accessibility requirements</h3><dl className="event-detail-grid">
          <Detail label="Room layout" value={event.room_layout ? label(event.room_layout) : null} />
          <Detail label="Required facilities" value={display('required_facilities', event.required_facilities)} />
          <Detail label="Wheelchair accessibility needed" value={event.need_wheelchair_accessibility ? 'Yes' : 'No'} />
          <Detail label="Accessibility for blind attendees needed" value={event.need_blind_accessibility ? 'Yes' : 'No'} />
        </dl><h3>Equipment and registration requirements</h3><dl className="event-detail-grid">
          <Detail label="Equipment requirements" value={display('equipment_requirements', event.equipment_requirements)} />
          <Detail label="Registration needs" value={event.registration_needs} />
        </dl></>}

        {edit.open && <form onSubmit={submitEdit} className="event-form">
          <p className="metadata">Changes to the proposed dates, expected attendance, venue requirements, accessibility needs or equipment requirements may affect arrangements already made. You will be asked to confirm those before they are saved.</p>
          {edit.error && <div role="alert" className="error">{edit.error}
            {edit.details && <ul>{Object.values(edit.details).map(message => <li key={message}>{message}</li>)}</ul>}</div>}
          <fieldset disabled={edit.busy} style={{ display: 'grid', gap: '12px', border: 0, padding: 0 }}>
            <EventFormSection title="1. Event details">
            <label>Event name<RequiredIndicator /><input value={edit.values.event_name} onChange={e => setField('event_name', e.target.value)} required /></label>
            <label>Purpose<RequiredIndicator /><input value={edit.values.purpose} onChange={e => setField('purpose', e.target.value)} required /></label>
            <label>Description<RequiredIndicator /><textarea rows="4" value={edit.values.description} onChange={e => setField('description', e.target.value)} required /></label>
            </EventFormSection>
            <EventFormSection title="2. Schedule and attendance">
            <label>Start date and time<RequiredIndicator /><input type="datetime-local" value={edit.values.start_datetime} onChange={e => setField('start_datetime', e.target.value)} required /></label>
            <label>End date and time<RequiredIndicator /><input type="datetime-local" value={edit.values.end_datetime} onChange={e => setField('end_datetime', e.target.value)} required /></label>
            <label>Expected attendance<RequiredIndicator /><input type="number" min="1" value={edit.values.capacity_needed} onChange={e => setField('capacity_needed', e.target.value)} required /></label>
            </EventFormSection>
            <EventFormSection title="3. Venue and accessibility">
            <label>Room layout<RequiredIndicator /><select value={edit.values.room_layout} onChange={e => setField('room_layout', e.target.value)} required>
              <option value="">Select a layout</option>{LAYOUTS.map(layout => <option key={layout} value={layout}>{label(layout)}</option>)}
            </select></label>
            <label>Required facilities (hold Ctrl or ⌘ to select several)
              <select multiple value={edit.values.required_facilities} onChange={e => setField('required_facilities', Array.from(e.target.selectedOptions, option => option.value))}>
                {FACILITIES.map(facility => <option key={facility} value={facility}>{label(facility)}</option>)}
              </select></label>
            {[['need_wheelchair_accessibility', 'Wheelchair accessibility needed'], ['need_blind_accessibility', 'Accessibility for blind attendees needed']].map(([name, text]) =>
              <label key={name}>{text}<select value={edit.values[name] ? 'yes' : 'no'} onChange={e => setField(name, e.target.value === 'yes')}><option value="no">No</option><option value="yes">Yes</option></select></label>)}
            </EventFormSection>
            <EventFormSection title="4. Equipment and registration">
            <label>Equipment requirements (one per line: type, quantity, notes — or write "none")
              <textarea rows="3" placeholder="projector, 2, HDMI input" value={edit.values.equipment_requirements} onChange={e => setField('equipment_requirements', e.target.value)} /></label>
            <label>Registration needs<textarea rows="3" value={edit.values.registration_needs} onChange={e => setField('registration_needs', e.target.value)} /></label>
            </EventFormSection>
          </fieldset>
          <div className="heading">
            <button type="button" className="secondary" onClick={discardEdits} disabled={edit.busy}>Cancel</button>
            <button type="submit" disabled={edit.busy}>{edit.busy ? 'Saving…' : 'Save changes'}</button>
          </div>
        </form>}
      </article>}


      {eventId && event && <section className="panel event-detail-section" id="event-equipment" tabIndex={-1}>
        <h2>Equipment requests</h2>


        <div className="event-equipment-request-list">
          {equipmentRequests.length === 0 ? (
            <p>No equipment requests for this event yet.</p>
          ) : (
            equipmentRequests.map((item) => (
              <div key={item.equipment_request_id || item.id} className="panel event-equipment-request-card">
                <h3>{item.equipment_type}</h3>
                <EquipmentRequestStatus request={item} />
                <p>Technical requirements: {item.technical_requirements || 'Not specified'}</p>
              </div>
            ))
          )}
        </div>
      </section>}

      {eventId && event && <section className="panel event-detail-section" id="event-history" tabIndex={-1}>
        <h2>Activity history</h2>
        {state.activityError && <div role="alert" className="error">{state.activityError} Use Refresh to try again.</div>}
        {!state.activityError && activity.length === 0 ? <p>No changes have been recorded for this event yet.</p> : activity.length > 0 && <dl>
          {activity.map(entry => <div key={entry.activity_id}>
            <dt>{entry.change_type === 'status_change' ? 'Status Change' : entry.change_type === 'critical_edit' ? `Critical Edit${entry.event_change_request_id ? ' — Change request Pending Review' : ''}` : 'Edit'} — {date(entry.created_at)}</dt>
            <dd>
              {userNames[entry.changed_by] || (entry.changed_by ? entry.changed_by.slice(0, 8) : 'System')}
              {entry.event_change_request_id && <p className="metadata">These are proposed values; the current event is unchanged while the request is reviewed.</p>}
              <ul>{Object.entries(entry.changes || {}).map(([field, change]) => <li key={field}>
                {label(field)}: {display(field, change.from)} → {display(field, change.to)}
              </li>)}</ul>
            </dd>
          </div>)}
        </dl>}
      </section>}
      </div><aside className="event-reference-sidebar" aria-label="People and arrangements">
      {event && <section className="panel event-reference-side-card"><h2>People</h2><dl>
          <Detail label="Event organiser" value={userNames[event.event_organiser_id] || (event.event_organiser_id ? event.event_organiser_id.slice(0, 8) : '-')} />
          <Detail label="Event coordinator" value={userNames[event.event_coordinator_id] || (event.event_coordinator_id ? event.event_coordinator_id.slice(0, 8) : '-')} />
          <Detail label="Technical support" value={userNames[event.technical_support_id] || (event.technical_support_id ? event.technical_support_id.slice(0, 8) : '-')} />
          <Detail label="Venue staff" value={userNames[event.venue_staff_id] || (event.venue_staff_id ? event.venue_staff_id.slice(0, 8) : '-')} />
          <Detail label="Safety officer" value={userNames[event.safety_officer_id] || (event.safety_officer_id ? event.safety_officer_id.slice(0, 8) : '-')} />
</dl></section>}
      {eventId && event && (venue.allowed || venueReadOnly) && <section className="panel event-detail-section" id="event-venue" tabIndex={-1}>
        <h2>Venue</h2>
        {venue.assigned && <p>Assigned venue: {canAccess(`/venues/${venue.assigned.venue_id}`)
          ? <Link to={`/venues/${venue.assigned.venue_id}`}>{venue.assigned.venue_name}</Link>
          : <strong>{venue.assigned.venue_name}</strong>}</p>}
        {/* An approved request is what makes a venue available for the event,
            and an event may need more than one, so each is named. */}
        {approvedVenues.length > 0 && <p>Approved by Venue Staff: <strong>{approvedVenues.join(', ')}</strong></p>}
        {!venue.assigned && approvedVenues.length === 0 && <p>No venue has been approved for this event yet.</p>}

        {/* Only an Event Coordinator may request a venue; Venue Staff assigned
            to the event read this section but decide requests elsewhere. */}
        {editable && venue.canRequest && can('event.findVenue', event) && <Link className="button-link" to={`/venue-search?event_id=${encodeURIComponent(eventId)}`}>
          Find venues for this event
        </Link>}
        {bookingToReview && can('booking.review', event) && <Link className="button-link" to={`/review-venue-bookings/${encodeURIComponent(bookingToReview.booking_id)}`}>
          Review venue bookings for this event
        </Link>}
        {venue.allowed && <>
        {!editable && <p className="metadata">A venue can only be requested while the event is in planning.</p>}

        <h3 style={{ marginTop: '20px' }}>Venue booking requests for this event</h3>
        {venue.error && <div role="alert" className="error">{venue.error} Use Refresh to try again.</div>}
        {!venue.error && venue.bookings.length === 0 && <p>No venue booking requests have been submitted for this event yet.</p>}
        {venue.bookings.length > 0 && <dl>
          {venue.bookings.map(booking => <div key={booking.booking_id}>
            <dt>{booking.venue_name}</dt>
            <dd>
              <span className={`booking-status booking-status-${booking.status}`}>{statusLabel(booking.status)}</span>
              {' · submitted '}{date(booking.submitted_at)}
              {booking.status !== 'submitted' && <>
                <br />Decided {date(booking.reviewed_at)}
                {booking.reviewed_by_name ? ` by ${booking.reviewed_by_name}` : ''}
                {booking.review_comments && <><br />Comments: <span style={{ whiteSpace: 'pre-wrap' }}>{booking.review_comments}</span></>}
              </>}
              <br />Reference: {booking.booking_id}
            </dd>
          </div>)}
        </dl>}
        </>}
      </section>}

      {event && <section className="panel event-reference-side-card"><h2>Equipment</h2>
        {state.equipmentError ? <p role="alert" className="error">{state.equipmentError}</p> : equipmentRequests.length ? <ul className="event-sidebar-equipment">{equipmentRequests.map(item => <li key={item.equipment_request_id}><span>{item.quantity} &times; {item.equipment_type}</span><span className={'event-stage event-stage-' + item.status}>{label(item.status)}</span></li>)}</ul> : <p>No equipment requests yet.</p>}
        {/* The event's coordinator requests equipment; its technical support
            reviews it. Each is taken to their own page, filtered to this event. */}
        {can('equipment.request', event)
          ? <Link className="button-link" to={`/equipment-requests?event_id=${encodeURIComponent(eventId)}`}>Request equipment for this event</Link>
          : can('equipment.review', event) && <Link className="button-link" to={`/equipment?event_id=${encodeURIComponent(eventId)}`}>Review equipment requests for this event</Link>}
      </section>}
      {event && <section className="panel event-detail-section" id="event-registration" tabIndex={-1}>
        <h2>Registration arrangements</h2>
        {event.registration_needs && <div style={{ marginBottom: '16px' }}>
          <p>Registration arrangements: {event.registration_ready ? 'Ready' : 'Awaiting coordinator confirmation'}</p>
          {can('event.registrationReady', event) && ['planning', 'confirmed'].includes(event.status) && <label>
            <input type="checkbox" checked={!!event.registration_ready} disabled={lifecycle.busy}
              onChange={e => updateLifecycle('registration-readiness', e.target.checked)} />
            Registration arrangements are ready
          </label>}
        </div>}
        {!event.registration_needs && <p>No registration requirements recorded.</p>}
      </section>}
      </aside></div>}
    </main>
  </>;
}
