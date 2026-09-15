import Navbar from '../components/Navbar';
import AppGrid from '../components/AppGrid';
import { HOME_APPS } from '../config/apps';

export default function Home({ onSignOut }) {
  return (
    <div className="home-page">
      <Navbar onSignOut={onSignOut} />

      <main className="home-content">
        <h1>ConnectSphere applications</h1>
        <p>Select an application to continue.</p>
        <AppGrid apps={HOME_APPS} />
      </main>
    </div>
  );
}
