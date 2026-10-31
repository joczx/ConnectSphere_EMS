import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { APP_CATEGORIES, HOME_APPS } from '../config/apps';
import { useAuth } from '../auth/AuthContext';
import UiIcon from './UiIcon';

export const APP_ICONS = {
  'event-registration': 'events', 'my-registrations': 'check',
  'assign-event-coordinators': 'requests', 'reassign-event-coordinators': 'events',
  events: 'events', 'event-requests': 'requests', 'review-event-requests': 'check',
  'event-change-requests': 'requests', 'review-event-change-requests': 'check',
  'venue-bookings': 'requests', equipment: 'equipment', 'equipment-requests': 'equipment', 'reserved-equipment': 'equipment', 'equipment-availability': 'equipment',
  'venue-management': 'venues', 'venue-search': 'search',
  'operational-safety-reviews': 'check',
};

export default function AppShell({ children }) {
  const { session, signOut, canAccess } = useAuth();
  const [open, setOpen] = useState(false);
  const user = session?.user;
  const name = user?.user_metadata?.full_name || user?.email || 'Signed in';
  const visibleApps = HOME_APPS.filter(app => canAccess(app.path));
  const groups = APP_CATEGORIES.map(category => ({ ...category,
    apps: visibleApps.filter(app => app.category === category.id),
  })).filter(group => group.apps.length > 0);
  return <div className="app-shell">
    <button className="mobile-nav-toggle" type="button" aria-label="Toggle navigation" aria-expanded={open} aria-controls="main-sidebar" onClick={() => setOpen(!open)}><UiIcon name="menu" /></button>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside id="main-sidebar" className={'portal-sidebar' + (open ? ' is-open' : '')}>
      <NavLink to="/home" className="sidebar-brand" onClick={() => setOpen(false)}><span>ConnectSphere</span><strong>Event Management</strong></NavLink>
      <nav aria-label="Main navigation">
        <NavLink to="/home" className="sidebar-link" onClick={() => setOpen(false)}><UiIcon name="home" />Dashboard</NavLink>
        {groups.map(group => <section className="sidebar-group" aria-labelledby={`sidebar-${group.id}`} key={group.id}>
          <h2 id={`sidebar-${group.id}`} className="sidebar-group-heading">{group.label}</h2>
          {group.apps.map(app => <NavLink key={app.id} to={app.path} className="sidebar-link" onClick={() => setOpen(false)}><UiIcon name={APP_ICONS[app.id]} /><span>{app.label}</span></NavLink>)}
        </section>)}
      </nav>
      <div className="sidebar-account"><span>Connected account</span><strong>{name}</strong>{user?.email && name !== user.email && <span>{user.email}</span>}<button onClick={signOut}>Sign out →</button></div>
    </aside>
    <div className="portal-workspace">{children}</div>
  </div>;
}
