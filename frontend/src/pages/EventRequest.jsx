import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { eventRequestsApi, humanise, userId } from '../services/eventRequests';

const LAYOUTS = ['theatre', 'classroom', 'boardroom', 'u_shape', 'banquet', 'standing'];
const FACILITIES = ['projector', 'sound_system', 'wifi', 'stage', 'microphone', 'whiteboard', 'video_conferencing'];

// datetime-local inputs use the browser's local time; the API stores UTC.
const toInput = (iso) => { if (!iso) return ''; const d = new Date(iso); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const toIso = (local) => local && new Date(local).toISOString();
// Equipment is edited as one "type, quantity, notes" line per item, or "none". Blank (null) means not answered yet.
const toLines = (items) => !items ? '' : items.length ? items.map(i => [i.equipment_type, i.quantity, i.notes].filter(Boolean).join(', ')).join('\n') : 'none';
const toItems = (text) => !text.trim() ? null : text.trim().toLowerCase() === 'none' ? [] : text.split('\n').filter(line => line.trim()).map(line => {
  const [equipment_type, quantity, ...notes] = line.split(',').map(part => part.trim());
  return { equipment_type, quantity: Number(quantity), notes: notes.join(', ') || null };
});

export default function EventRequest() {
  const { api, token } = useAuth();
  const { requestId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const isNew = requestId === 'new';
  const [state, setState] = useState({ loading: !isNew });
  useEffect(() => {
    if (isNew) return setState({});
    (async () => {
      try {
        const request = await eventRequestsApi(api, '/' + requestId);
        // A rejected request shows the Coordinator's remarks, so the Organiser knows what to amend.
        setState({ request, remarks: request.status === 'rejected' && (await eventRequestsApi(api, `/${requestId}/reviews`)).reviews[0]?.comments });
      }
      catch (err) { setState({ error: err.message || 'Unable to load this event request.' }); }
    })();
  }, [api, requestId, isNew, location.key]);

  async function save(e) {
    e.preventDefault();
    const submit = e.nativeEvent.submitter.value === 'submit';
    if (submit && !window.confirm('Submit this event request for review? You will not be able to edit it afterwards.')) return;
    const form = new FormData(e.currentTarget);
    const values = Object.fromEntries(form);
    const facilities = form.getAll('required_facilities');
    const body = {
      ...values, start_datetime: toIso(values.start_datetime), end_datetime: toIso(values.end_datetime),
      required_facilities: facilities.length ? facilities.filter(f => f !== 'none') : null, equipment_requirements: toItems(values.equipment_requirements),
      need_wheelchair_accessibility: values.need_wheelchair_accessibility === 'yes', need_blind_accessibility: values.need_blind_accessibility === 'yes',
    };
    setState(current => ({ ...current, busy: true, error: null, details: null }));
    try {
      let data = isNew
        ? await eventRequestsApi(api, '', { method: 'POST', body: { ...body, event_organiser_id: userId(token), save_as_draft: !submit } })
        : await eventRequestsApi(api, '/' + requestId, { method: 'PATCH', body });
      if (submit && !isNew) data = await eventRequestsApi(api, `/${requestId}/submit`, { method: 'POST' });
      navigate('/event-requests/' + data.event_request.event_request_id, { replace: true, state: { message: data.message } });
    } catch (err) {
      setState(current => ({ ...current, busy: false, error: err.message, details: err.details }));
    }
  }

  const request = state.request || {};
  const value = (name) => request[name] ?? '';
  const rejected = request.status === 'rejected';
  const editable = isNew || request.status === 'draft' || rejected;
  return <>
    <Navbar />
    <main className="container">
      <Link to="/event-requests">← My event requests</Link>
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{isNew ? 'New event request' : request.event_name || 'Event request'}</h1></div></div>
      {request.status && <p className="metadata">Status: {humanise(request.status)}</p>}
      {location.state?.message && <p role="status" className="panel">{location.state.message}</p>}
      {state.remarks && <div className="panel"><p className="eyebrow">COORDINATOR REMARKS</p><p>{state.remarks}</p></div>}
      {state.loading && <p role="status">Loading event request…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}
        {state.details && <ul>{Object.values(state.details).map(message => <li key={message}>{message}</li>)}</ul>}</div>}
      {(isNew || state.request) && <form className="panel" key={request.updated_at} onSubmit={save}>
        <fieldset disabled={!editable || state.busy}>
          <label>Event name<input name="event_name" required defaultValue={value('event_name')} /></label>
          <label>Purpose<input name="purpose" required defaultValue={value('purpose')} /></label>
          <label>Description<textarea name="description" rows="4" required defaultValue={value('description')} /></label>
          <label>Start date and time<input name="start_datetime" type="datetime-local" required defaultValue={toInput(request.start_datetime)} /></label>
          <label>End date and time<input name="end_datetime" type="datetime-local" required defaultValue={toInput(request.end_datetime)} /></label>
          <label>Expected attendance<input name="capacity_needed" type="number" min="1" required defaultValue={value('capacity_needed')} /></label>
          <label>Room layout<select name="room_layout" required defaultValue={value('room_layout')}>
            <option value="">Select a layout</option>{LAYOUTS.map(layout => <option key={layout} value={layout}>{humanise(layout)}</option>)}
          </select></label>
          <label>Required facilities (hold Ctrl or ⌘ to select several)<select name="required_facilities" multiple required defaultValue={request.required_facilities?.length === 0 ? ['none'] : request.required_facilities || []}>
            <option value="none">No facilities needed</option>{FACILITIES.map(facility => <option key={facility} value={facility}>{humanise(facility)}</option>)}
          </select></label>
          {[['need_wheelchair_accessibility', 'Wheelchair accessibility needed'], ['need_blind_accessibility', 'Accessibility for blind attendees needed']].map(([name, text]) =>
            <label key={name}>{text}<select name={name} defaultValue={request[name] ? 'yes' : 'no'}><option value="no">No</option><option value="yes">Yes</option></select></label>)}
          <label>Equipment requirements (one per line: type, quantity, notes — or write "none")<textarea name="equipment_requirements" rows="3" required placeholder="projector, 2, HDMI input" defaultValue={toLines(request.equipment_requirements)} /></label>
          <label>Registration needs (write "none" if not needed)<textarea name="registration_needs" rows="3" required defaultValue={value('registration_needs')} /></label>
          {editable && <div className="heading">
            <button type="submit" value="draft" className="secondary" formNoValidate>{state.busy ? 'Saving…' : rejected ? 'Save changes' : 'Save draft'}</button>
            <button type="submit" value="submit">{rejected ? 'Resubmit request' : 'Submit request'}</button>
          </div>}
        </fieldset>
      </form>}
    </main>
  </>;
}
