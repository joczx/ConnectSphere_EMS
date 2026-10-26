import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { when } from '../services/venueBookings';
import { useFeedback } from './FeedbackProvider';
import UiIcon from './UiIcon';

// One notification, as the bell popup and the full notifications page both show it.
export function NotificationItem({ item, onOpen }) {
  return <li className={item.read_at ? undefined : 'unread'}>
    <button type="button" onClick={() => onOpen(item)}>
      <strong>{item.title}</strong>
      <span>{item.body}</span>
      <small>{when(item.created_at)}</small>
    </button>
  </li>;
}

export default function AccountMenu() {
  const { notify } = useFeedback();
  const { api, session, account, signOut } = useAuth();
  const [notifications, setNotifications] = useState({ items: [], unread: 0, error: '' });
  const navigate = useNavigate();
  const bell = useRef(null);

  useEffect(() => {
    let ignore = false;
    if (!session?.access_token) {
      setNotifications({ items: [], unread: 0, error: '' });
      return () => { ignore = true; };
    }

    const loadNotifications = () => {
      api('/api/notifications?limit=10', { cache: 'no-store' })
        .then(data => {
          if (!ignore) setNotifications({ items: data.items || [], unread: data.unread || 0, error: '' });
        })
        .catch(() => {
          if (!ignore) setNotifications({ items: [], unread: 0, error: 'Unable to load notifications.' });
        });
    };
    loadNotifications();
    const timer = setInterval(loadNotifications, 60000);
    window.addEventListener('focus', loadNotifications);
    // The notifications page marks items read; the badge follows straight away.
    window.addEventListener('notifications:changed', loadNotifications);

    return () => {
      ignore = true;
      clearInterval(timer);
      window.removeEventListener('focus', loadNotifications);
      window.removeEventListener('notifications:changed', loadNotifications);
    };
  }, [api, session?.access_token]);

  function go(path) {
    bell.current.open = false;
    if (path) navigate(path);
  }

  // Opening a notification from the popup reads it, as viewing it on the full page does.
  async function open(item) {
    go(item.link);
    if (item.read_at) return;
    try {
      await api(`/api/notifications/${item.notification_id}/read`, { method: 'POST', feedback: false });
      window.dispatchEvent(new Event('notifications:changed'));
    } catch {
      // It simply stays unread.
    }
  }

  // Notifications have their own bell, so a long list can never push Sign out out of reach.
  return (
    <div className="account-actions">
      <details className="notification-menu" ref={bell}>
        <summary aria-label={`Notifications (${notifications.unread} unread)`}>
          <UiIcon name="bell" />{notifications.unread > 0 && <span className="notification-count">{notifications.unread}</span>}
        </summary>
        <div className="account-menu-content account-notifications">
          <strong>Notifications</strong>
          {notifications.items.length === 0 && !notifications.error && <span>No notifications yet.</span>}
          {notifications.items.length > 0 && <ul className="notification-list">
            {notifications.items.map(item => <NotificationItem key={item.notification_id} item={item} onOpen={open} />)}
          </ul>}
          {notifications.error && <span role="status">{notifications.error}</span>}
          <button type="button" className="secondary" onClick={() => go('/notifications')}>View all notifications</button>
        </div>
      </details>
      <details className="account-menu">
        <summary>
          <span>{account.user?.name}</span>
          {account.user?.roles?.length > 0 && (
            <span className="account-menu-roles">{account.user.roles.join(', ')}</span>
          )}
        </summary>
        <div className="account-menu-content">
          <span>Signed in</span>
          {account.error && <span role="status">{account.error}</span>}
          <button type="button" className="secondary" onClick={() => { signOut(); notify('You have been signed out.', 'success', 'Signed out'); }}>
            Sign out
          </button>
        </div>
      </details>
    </div>
  );
}
