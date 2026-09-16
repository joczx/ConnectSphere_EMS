import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { api, humanise, userId } from '../services/eventRequests';

const when = (iso) => iso && new Intl.DateTimeFormat('en-SG', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore' }).format(new Date(iso));
const list = (items, show) => items?.length ? items.map(show).join(', ') : 'None';

export default function ReviewEventRequest({ token, onSignOut }) {
  const { requestId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    (async () => {
      try { setState({ request: await api('/' + requestId, token) }); }
      catch (err) { setState({ error: err.message || 'Unable to load this event request.' }); }
    })();
  }, [requestId, token, location.key]);

  async function review(e) {
    e.preventDefault();
    const outcome = e.nativeEvent.submitter.value;
    if (!window.confirm(`${outcome === 'approved' ? 'Approve' : 'Reject'} this event request? This cannot be changed afterwards.`)) return;
    const comments = new FormData(e.currentTarget).get('comments');
    setState(current => ({ ...current, busy: true, error: null, details: null }));
    try {
      const data = await api(`/${requestId}/review`, token, { method: 'POST', body: { reviewer_id: userId(token), outcome, comments } });
      navigate('/review-event-requests/' + requestId, { replace: true, state: { message: data.message } });
    } catch (err) {
      setState(current => ({ ...current, busy: false, error: err.message, details: err.details }));
    }
  }

  const request = state.request;
  return <>
    <Navbar onSignOut={onSignOut} />
    <main className="container">
      <Link to="/review-event-requests">← Review event requests</Link>
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>{request?.event_name || 'Event request'}</h1></div></div>
      {location.state?.message && <p role="status" className="panel">{location.state.message}</p>}
      {state.loading && <p role="status">Loading event request…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}
        {state.details && <ul>{Object.values(state.details).map(message => <li key={message}>{message}</li>)}</ul>}</div>}
      {request && <article className="panel"><dl>{[
        ['Status', humanise(request.status)],
        ['Submitted', when(request.submitted_at)],
        ['Purpose', request.purpose],
        ['Description', request.description],
        ['Start date and time', when(request.start_datetime)],
        ['End date and time', when(request.end_datetime)],
        ['Expected attendance', request.capacity_needed],
        ['Room layout', request.room_layout && humanise(request.room_layout)],
        ['Required facilities', list(request.required_facilities, humanise)],
        ['Equipment requirements', list(request.equipment_requirements, i => `${i.equipment_type} × ${i.quantity}${i.notes ? ` (${i.notes})` : ''}`)],
        ['Wheelchair accessibility needed', request.need_wheelchair_accessibility ? 'Yes' : 'No'],
        ['Accessibility for blind attendees needed', request.need_blind_accessibility ? 'Yes' : 'No'],
        ['Registration needs', request.registration_needs],
      ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Not specified'}</dd></div>)}</dl></article>}
      {['submitted', 'under_review'].includes(request?.status) && <form className="panel" onSubmit={review}>
        <fieldset disabled={state.busy}>
          <label>Remarks (required when rejecting)<textarea name="comments" rows="4" /></label>
          <div className="heading">
            <button type="submit" value="rejected" className="secondary">Reject</button>
            <button type="submit" value="approved">Approve</button>
          </div>
        </fieldset>
      </form>}
    </main>
  </>;
}
