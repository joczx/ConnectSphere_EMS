import DashboardOverview from '../components/DashboardOverview';
import OrganiserDashboard from '../components/OrganiserDashboard';
import MyRegistrations from './MyRegistrations';
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
  const { canAccess } = useAuth();
  const attendeeDashboard = canAccess('/my-registrations') && !canAccess('/events');
  const organiserDashboard = canAccess('/event-requests');
  return (
    <div className="home-page">
      <Navbar />

      <main className="home-content">
        <div className="heading dashboard-heading"><div><h1>Welcome back</h1><p>{attendeeDashboard ? 'View your event registrations and attendance status.' : organiserDashboard ? 'Plan your events and monitor attendee registrations.' : 'Manage your events, venues, and equipment in one place.'}</p></div><WorkspaceLink className="button-link" to="/event-requests/new">+ Create event request</WorkspaceLink></div>
        {attendeeDashboard ? <MyRegistrations embedded /> : organiserDashboard ? <OrganiserDashboard /> : <DashboardOverview />}
        <section className="dashboard-applications"><div className="dashboard-section-heading"><h2>Your workspace</h2><span>Select an application to continue</span></div><AppGrid apps={HOME_APPS} /></section>
      </main>
    </div>
  );
}
