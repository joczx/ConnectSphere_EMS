import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useFeedback } from './FeedbackProvider';
import UiIcon from './UiIcon';

export default function AccountMenu() {
  const { notify } = useFeedback();
  const { api, session, account, signOut } = useAuth();
  const [notifications, setNotifications] = useState({ items: [], error: '' });

  useEffect(() => {
    let ignore = false;
    if (!session?.access_token) {
      setNotifications({ items: [], error: '' });
      return () => { ignore = true; };
    }

    const loadNotifications = () => {
      api('/api/notifications?unread=1', { cache: 'no-store' })
        .then(data => {
          if (!ignore) setNotifications({ items: data.notifications || [], error: '' });
        })
        .catch(() => {
          if (!ignore) setNotifications({ items: [], error: 'Unable to load notifications.' });
        });
    };
    loadNotifications();
    const timer = setInterval(loadNotifications, 60000);
    window.addEventListener('focus', loadNotifications);

    return () => {
      ignore = true;
      clearInterval(timer);
      window.removeEventListener('focus', loadNotifications);
    };
  }, [api, session?.access_token]);

  // Notifications have their own bell, so a long list can never push Sign out out of reach.
  return (
    <div className="account-actions">
      <details className="notification-menu">
        <summary aria-label={`Notifications (${notifications.items.length} new)`}>
          <UiIcon name="bell" />{notifications.items.length > 0 && <span className="notification-count">{notifications.items.length}</span>}
        </summary>
        <div className="account-menu-content account-notifications">
          <strong>New notifications</strong>
          {notifications.items.length === 0 && !notifications.error && <span>No new notifications.</span>}
          {notifications.items.length > 0 && <ul>
            {notifications.items.map(item => <li key={item.notification_id}>{item.message}</li>)}
          </ul>}
          {notifications.error && <span role="status">{notifications.error}</span>}
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
