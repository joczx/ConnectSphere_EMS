import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { registrationDate } from './RegistrationPeriod';

const statuses = { registered: 'Confirmed', waiting_list: 'Waitlisted', withdrawn: 'Withdrawn' };

export default function EventRegistrationRoster({ eventId }) {
  const { api } = useAuth();
  const [state, setState] = useState({ loading: true });
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    api(`/api/events/${eventId}/registrations`, { signal: controller.signal, cache: 'no-store' })
      .then(data => { if (!controller.signal.aborted) setState({ data, loading: false }); })
      .catch(error => { if (!controller.signal.aborted) setState({ error: error.message || 'Unable to load registrations.', loading: false }); });
    const reload = () => setRefresh(value => value + 1);
    const timer = setInterval(reload, 30000);
    window.addEventListener('focus', reload);
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', reload); };
  }, [api, eventId, refresh]);

  return <section className="panel event-detail-section" aria-label="Attendee registrations">
    <div className="heading"><h2>Attendee registrations</h2>
      <button type="button" className="secondary" disabled={state.loading} onClick={() => setRefresh(value => value + 1)}>Refresh registrations</button>
    </div>
    <p>Registration information refreshes every 30 seconds. Confirmed totals exclude waitlisted and withdrawn attendees.</p>
    {state.loading && <p role="status">Loading registrations…</p>}
    {state.error && <p role="alert" className="error">{state.error}</p>}
    {state.data && <>
      <dl className="detail-grid">
        <div><dt>Total registered attendees</dt><dd>{state.data.total_registered}</dd></div>
        <div><dt>Waitlisted</dt><dd>{state.data.total_waitlisted}</dd></div>
        <div><dt>Withdrawn</dt><dd>{state.data.total_withdrawn}</dd></div>
      </dl>
      {!state.data.registrations.length ? <p>No registration records for this event.</p> :
        <div style={{ overflowX: 'auto' }}><table>
          <caption>Registration records for {state.data.event.event_name}</caption>
          <thead><tr><th scope="col">Attendee name</th><th scope="col">Contact email</th><th scope="col">Contact phone</th><th scope="col">Registration status</th><th scope="col">Registered</th></tr></thead>
          <tbody>{state.data.registrations.map(item => <tr key={item.attendee_id}>
            <td>{item.full_name || 'Not provided'}</td>
            <td>{item.contact_email || 'Not provided'}</td>
            <td>{item.contact_phone || 'Not provided'}</td>
            <td>{statuses[item.status] || 'Unknown'}</td>
            <td>{registrationDate(item.registered_at)}</td>
          </tr>)}</tbody>
        </table></div>}
    </>}
  </section>;
}
