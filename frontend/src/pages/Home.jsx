import Navbar from '../components/Navbar';
import AppGrid from '../components/AppGrid';
import { HOME_APPS } from '../config/apps';
import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <div className="home-page">
      <Navbar />

      <main className="home-content">
        <div className="heading dashboard-heading"><div><h1>Welcome back</h1><p>Manage your events, venues, and equipment in one place.</p></div><Link className="button-link" to="/event-requests/new">+ Create event request</Link></div>
        <div className="dashboard-summary">
          <Link to="/events" className="summary-card"><span>Event planning</span><strong>My events</strong><small>View event details and progress →</small></Link>
          <Link to="/event-requests" className="summary-card"><span>Requests & drafts</span><strong>Event requests</strong><small>Continue drafts and track submissions →</small></Link>
          <Link to="/venues" className="summary-card"><span>Spaces & facilities</span><strong>Venues</strong><small>Explore and manage your venue catalogue →</small></Link>
          <Link to="/equipment-availability" className="summary-card"><span>Resources</span><strong>Equipment</strong><small>Check availability for your next event →</small></Link>
        </div>
        <section className="dashboard-applications"><div className="dashboard-section-heading"><h2>Your workspace</h2><span>Select an application to continue</span></div><AppGrid apps={HOME_APPS} /></section>
      </main>
    </div>
  );
}
