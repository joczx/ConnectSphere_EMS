import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { NotificationItem } from '../components/AccountMenu';
import { useAuth } from '../auth/AuthContext';

// Every notification from the last 14 days, 20 per page. Opening one here marks
// it read and goes to the item it is about.
export default function Notifications() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get('page')) || 1);
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    api(`/api/notifications?page=${page}`, { cache: 'no-store', signal: controller.signal })
      .then(data => {
        if (controller.signal.aborted) return;
        setState({ data });
        // Viewing them here reads them. They stay highlighted for this visit, so
        // what was new when the page opened can still be told apart.
        const unread = data.items.filter(item => !item.read_at);
        if (unread.length) {
          Promise.all(unread.map(item => api(`/api/notifications/${item.notification_id}/read`, { method: 'POST', feedback: false })))
            .then(() => window.dispatchEvent(new Event('notifications:changed')))
            .catch(() => {});
        }
      })
      .catch(err => { if (!controller.signal.aborted) setState({ error: err.message || 'Unable to load notifications.' }); });
    return () => controller.abort();
  }, [api, page]);

  async function open(item) {
    if (!item.read_at) {
      try {
        await api(`/api/notifications/${item.notification_id}/read`, { method: 'POST', feedback: false });
        window.dispatchEvent(new Event('notifications:changed'));
      } catch {
        // Still go to the item; it simply stays unread.
      }
    }
    if (item.link) navigate(item.link);
    else setState(current => ({ data: { ...current.data, items: current.data.items.map(other =>
      other.notification_id === item.notification_id ? { ...other, read_at: new Date().toISOString() } : other) } }));
  }

  const data = state.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return <>
    <Navbar />
    <main className="container">
      <div className="heading"><div><p className="eyebrow">NOTIFICATIONS</p><h1>Notifications</h1></div></div>
      <p>Notifications from the last 14 days.</p>
      {state.loading && <p role="status">Loading notifications…</p>}
      {state.error && <div role="alert" className="panel error">{state.error}</div>}
      {data && !data.items.length && <p className="panel">No notifications in the last 14 days.</p>}
      {data?.items.length > 0 && <ul className="notification-list notification-page-list">
        {data.items.map(item => <NotificationItem key={item.notification_id} item={item} onOpen={open} />)}
      </ul>}
      {pages > 1 && <div className="venue-page-actions">
        <button type="button" className="secondary" disabled={page <= 1} onClick={() => setParams({ page: page - 1 })}>Previous</button>
        <span>Page {page} of {pages}</span>
        <button type="button" className="secondary" disabled={page >= pages} onClick={() => setParams({ page: page + 1 })}>Next</button>
      </div>}
    </main>
  </>;
}
