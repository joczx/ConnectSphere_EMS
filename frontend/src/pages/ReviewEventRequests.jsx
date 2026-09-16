import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { api, humanise } from '../services/eventRequests';

export default function ReviewEventRequests({ token, onSignOut }) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    (async () => {
      try { setState({ requests: (await api('?status=submitted', token)).event_requests }); }
      catch (err) { setState({ error: err.message || 'Unable to load submitted event requests.' }); }
    })();
  }, [token]);
  return <>
    <Navbar onSignOut={onSignOut} />
    <main className="container">
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>Review event requests</h1></div></div>
      {state.loading && <p role="status">Loading submitted event requests…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {state.requests?.length > 0 && <section className="event-list">{state.requests.map(item => <Link className="panel event-link" key={item.event_request_id} to={'/review-event-requests/' + item.event_request_id}>
        <h2>{item.event_name}</h2>
        <p className="metadata">Status: {humanise(item.status)}</p>
        <span>Review request →</span>
      </Link>)}</section>}
    </main>
  </>;
}
