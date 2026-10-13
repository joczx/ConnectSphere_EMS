import Navbar from '../components/Navbar';
import AppGrid from '../components/AppGrid';
import { HOME_APPS } from '../config/apps';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

function WorkspaceLink(props) {
  const { canAccess } = useAuth();
  return canAccess(props.to) ? <Link {...props} /> : null;
}

export default function Home() {
  return (
    <div className="home-page">
      <Navbar />

      <main className="home-content">
        <div className="heading dashboard-heading"><div><h1>Welcome back</h1><p>Manage your events, venues, and equipment in one place.</p></div><WorkspaceLink className="button-link" to="/event-requests/new">+ Create event request</WorkspaceLink></div>
        <div className="dashboard-summary">
          <WorkspaceLink to="/events" className="summary-card"><span>Event planning</span><strong>My events</strong><small>View event details and progress →</small></WorkspaceLink>
          <WorkspaceLink to="/event-requests" className="summary-card"><span>Requests & drafts</span><strong>Event requests</strong><small>Continue drafts and track submissions →</small></WorkspaceLink>
          <WorkspaceLink to="/venues" className="summary-card"><span>Spaces & facilities</span><strong>Venues</strong><small>Explore and manage your venue catalogue →</small></WorkspaceLink>
          <WorkspaceLink to="/equipment-availability" className="summary-card"><span>Resources</span><strong>Equipment</strong><small>Check availability for your next event →</small></WorkspaceLink>
        </div>
        <section className="dashboard-applications"><div className="dashboard-section-heading"><h2>Your workspace</h2><span>Select an application to continue</span></div><AppGrid apps={HOME_APPS} /></section>
      </main>
    </div>
  );
}
