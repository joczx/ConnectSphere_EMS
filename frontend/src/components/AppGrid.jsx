import AppTile from './AppTile';

export default function AppGrid({ apps = [] }) {
  return (
    <section className="app-grid" aria-label="Applications">
      {apps.map((app) => <AppTile key={app.id} app={app} />)}
    </section>
  );
}
