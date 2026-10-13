import { Link } from 'react-router-dom';
import UiIcon from './UiIcon';
import { APP_ICONS } from './AppShell';

export default function AppTile({ app }) {
  return (
    <Link className="app-tile" to={app.path} aria-label={app.description}>
      <span className="app-tile-icon" aria-hidden="true"><UiIcon name={APP_ICONS[app.id]} /></span>
      <span className="app-tile-label">{app.label}</span>
      <span className="app-tile-description">{app.description}</span>
    </Link>
  );
}
