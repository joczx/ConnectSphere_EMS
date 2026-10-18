import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { HOME_APPS } from '../config/apps';
import { useAuth } from '../auth/AuthContext';
import UiIcon from './UiIcon';

export const APP_ICONS = {
  'assign-event-coordinators': 'requests', 'reassign-event-coordinators': 'events',
  events: 'events', 'event-requests': 'requests', 'review-event-requests': 'check',
  'event-change-requests': 'requests', 'review-event-change-requests': 'check',
  'venue-bookings': 'requests', equipment: 'equipment', 'equipment-availability': 'equipment',
  'venue-management': 'venues', 'venue-search': 'search', 'venue-suitability': 'check',
  'operational-safety-reviews': 'check',
};

export default function AppShell({ children }) {
  const { session, signOut, canAccess } = useAuth();
  const [open, setOpen] = useState(false);
  const user = session?.user;
  const name = user?.user_metadata?.full_name || user?.email || 'Signed in';
  return <div className="app-shell">
    <button className="mobile-nav-toggle" type="button" aria-label="Toggle navigation" aria-expanded={open} aria-controls="main-sidebar" onClick={() => setOpen(!open)}><UiIcon name="menu" /></button>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside id="main-sidebar" className={'portal-sidebar' + (open ? ' is-open' : '')}>
      <NavLink to="/home" className="sidebar-brand" onClick={() => setOpen(false)}><span>ConnectSphere</span><strong>Event Management</strong></NavLink>
      <nav aria-label="Main navigation">
        <NavLink to="/home" className="sidebar-link" onClick={() => setOpen(false)}><UiIcon name="home" />Dashboard</NavLink>
        {HOME_APPS.filter(app => canAccess(app.path)).map(app => <NavLink key={app.id} to={app.path} className="sidebar-link" onClick={() => setOpen(false)}><UiIcon name={APP_ICONS[app.id]} /><span>{app.label}</span></NavLink>)}
      </nav>
      <div className="sidebar-account"><span>Connected account</span><strong>{name}</strong>{user?.email && name !== user.email && <span>{user.email}</span>}<button onClick={signOut}>Sign out →</button></div>
    </aside>
    <div className="portal-workspace">{children}</div>
  </div>;
}
