import { useEffect, useState } from 'react';
import AppTile from './AppTile';
import { useAuth } from '../auth/AuthContext';

export default function AppGrid({ apps = [] }) {
  const { api } = useAuth();
  const [state, setState] = useState({ loading: true, roles: [], error: '' });

  useEffect(() => {
    let ignore = false;
    api('/api/users/me', { cache: 'no-store' })
      .then(data => {
        if (!ignore) setState({ loading: false, roles: data.user?.roles || [], error: '' });
      })
      .catch(err => {
        if (!ignore) setState({
          loading: false,
          roles: [],
          error: err.message || 'Unable to load your applications.',
        });
      });
    return () => { ignore = true; };
  }, [api]);

  const visibleApps = apps.filter(app => (
    !app.roles?.length || app.roles.some(role => state.roles.includes(role))
  ));

  return (
    <section className="app-grid" aria-label="Applications">
      {state.loading
        ? <p role="status">Loading applications…</p>
        : state.error
          ? <p role="alert">Unable to load your applications. {state.error}</p>
          : visibleApps.map((app) => <AppTile key={app.id} app={app} />)}
    </section>
  );
}
