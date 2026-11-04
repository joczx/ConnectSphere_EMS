import { Link } from 'react-router-dom';

export const registrationLabels = { registered: 'Confirmed', waiting_list: 'Waitlisted', withdrawn: 'Withdrawn' };

export function RegistrationNavigation({ current }) {
  return <nav className="attendee-navigation" aria-label="Registration pages">
    <Link to="/event-registration" aria-current={current === 'events' ? 'page' : undefined}>Browse events</Link>
    <Link to="/my-registrations" aria-current={current === 'registrations' ? 'page' : undefined}>My registrations</Link>
  </nav>;
}

export function EventDateTile({ value }) {
  const date = value ? new Date(value) : null;
  const valid = date && !Number.isNaN(date.getTime());
  return <div className="attendee-date" aria-hidden="true">
    <span>{valid ? date.toLocaleDateString('en-SG', { month: 'short', timeZone: 'Asia/Singapore' }) : 'Date'}</span>
    <strong>{valid ? date.toLocaleDateString('en-SG', { day: '2-digit', timeZone: 'Asia/Singapore' }) : '—'}</strong>
  </div>;
}

export function RegistrationBadge({ status }) {
  return <span className={`registration-status registration-status-${status}`}>Registration status: {registrationLabels[status] || 'Unknown'}</span>;
}
