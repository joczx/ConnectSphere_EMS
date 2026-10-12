import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';

export default function AccountMenu() {
  const { api, session, signOut } = useAuth();
  const [account, setAccount] = useState({ user: null, error: '' });

  useEffect(() => {
    let ignore = false;
    if (!session?.access_token) {
      setAccount({ user: null, error: '' });
      return () => { ignore = true; };
    }

    api('/api/users/me', { cache: 'no-store' })
      .then(data => {
        if (!ignore) setAccount({ user: data.user, error: '' });
      })
      .catch(() => {
        if (!ignore) setAccount({ user: null, error: 'Unable to load account details.' });
      });

    return () => { ignore = true; };
  }, [api, session?.access_token]);

  return (
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
        <button type="button" className="secondary" onClick={signOut}>
          Sign out
        </button>
      </div>
    </details>
  );
}
