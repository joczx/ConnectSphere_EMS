import { useEffect, useState } from 'react';
import AppTile from './AppTile';
import { useAuth } from '../auth/AuthContext';

export default function AppGrid({ apps = [] }) {
  const { api } = useAuth();
  const [roles, setRoles] = useState(null);

  useEffect(() => {
    let ignore = false;
    api('/api/users/me', { cache: 'no-store' })
      .then(data => { if (!ignore) setRoles(data.user?.roles || []); })
      .catch(() => { if (!ignore) setRoles([]); });
    return () => { ignore = true; };
  }, [api]);

  const visibleApps = apps.filter(app => (
    !app.roles?.length || (roles && app.roles.some(role => roles.includes(role)))
  ));

  return (
    <section className="app-grid" aria-label="Applications">
      {visibleApps.map((app) => <AppTile key={app.id} app={app} />)}
    </section>
  );
}
