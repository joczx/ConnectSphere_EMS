import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { eventRequestsApi, humanise } from '../services/eventRequests';

export default function ReviewEventRequests() {
  const { api } = useAuth();
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    (async () => {
      // One call per status, so Organisers' drafts never reach a Coordinator's browser.
      try { setState({ sections: await Promise.all([['Received', 'submitted'], ['Approved', 'approved'], ['Rejected', 'rejected']].map(async ([title, status]) => [title, (await eventRequestsApi(api, '?status=' + status)).event_requests])) }); }
      catch (err) { setState({ error: err.message || 'Unable to load event requests.' }); }
    })();
  }, [api]);
  return <>
    <Navbar />
    <main className="container">
      <div className="heading"><div><p className="eyebrow">EVENT PLANNING</p><h1>Review event requests</h1></div></div>
      {state.loading && <p role="status">Loading event requests…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {state.sections?.map(([title, items]) => items.length > 0 && <section key={title}>
        <h2>{title}</h2>
        <div className="event-list">{items.map(item => <Link className="panel event-link" key={item.event_request_id} to={'/review-event-requests/' + item.event_request_id}>
          <h2>{item.event_name}</h2>
          <p className="metadata">Status: {humanise(item.status)}</p>
          <span>{item.status === 'submitted' ? 'Review request →' : 'View request →'}</span>
        </Link>)}</div>
      </section>)}
    </main>
  </>;
}
