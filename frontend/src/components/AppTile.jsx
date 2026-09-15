import { Link } from 'react-router-dom';

export default function AppTile({ app }) {
  return (
    <Link className="app-tile" to={app.path} aria-label={app.description}>
      <span className="app-tile-icon" aria-hidden="true">{app.icon}</span>
      <span className="app-tile-label">{app.label}</span>
    </Link>
  );
}
