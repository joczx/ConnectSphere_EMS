import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { api, humanise, userId } from '../services/eventRequests';

export default function EventRequests({ token, onSignOut }) {
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    (async () => {
      try { setState({ requests: (await api('?event_organiser_id=' + userId(token), token)).event_requests }); }
      catch (err) { setState({ error: err.message || 'Unable to load your event requests.' }); }
    })();
  }, [token]);
  async function remove(item) {
    if (!window.confirm(`Delete the draft "${item.event_name || 'Untitled request'}"? This cannot be undone.`)) return;
    try {
      await api('/' + item.event_request_id, token, { method: 'DELETE' });
      setState(current => ({ requests: current.requests.filter(r => r.event_request_id !== item.event_request_id) }));
    } catch (err) { setState(current => ({ ...current, error: err.message })); }
  }
  const requests = state.requests || [];
  const section = (title, items) => items.length > 0 && <section>
    <h2>{title}</h2>
    <div className="event-list">{items.map(item => <div className="request-card" key={item.event_request_id}>
      <Link className="panel event-link" to={'/event-requests/' + item.event_request_id}>
        <h2>{item.event_name || 'Untitled request'}</h2>
        <p className="metadata">Status: {humanise(item.status)}</p>
        <span>{item.status === 'draft' ? 'Continue editing →' : 'View request →'}</span>
      </Link>
      {item.status === 'draft' && <button className="delete-draft" title="Delete draft" aria-label={`Delete draft ${item.event_name || 'Untitled request'}`} onClick={() => remove(item)}>−</button>}
    </div>)}</div>
  </section>;
  return <>
    <Navbar onSignOut={onSignOut} />
    <main className="container">
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>My event requests</h1></div>
        <button onClick={() => navigate('/event-requests/new')}>New event request</button></div>
      {state.loading && <p role="status">Loading your event requests…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {section('Drafts', requests.filter(item => item.status === 'draft'))}
      {section('Submitted', requests.filter(item => item.status !== 'draft'))}
    </main>
  </>;
}
