import AppTile from './AppTile';
import { useAuth } from '../auth/AuthContext';

export default function AppGrid({ apps = [] }) {
  const { canAccess } = useAuth();
  return (
    <section className="app-grid" aria-label="Applications">
      {apps.filter(app => canAccess(app.path)).map((app) => <AppTile key={app.id} app={app} />)}
    </section>
  );
}
