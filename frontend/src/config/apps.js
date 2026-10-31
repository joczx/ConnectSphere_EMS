import { rolesForPath } from '../auth/access';

/**
 * Home-page app definition shape:
 * {
 *   id: string,
 *   label: string,
 *   description: string,
 *   path: string,
 *   icon: string,
 *   category: string,
 *   roles: string[]
 * }
 */
export const APP_CATEGORIES = [
  { id: 'events', label: 'Events' },
  { id: 'registration', label: 'Registration' },
  { id: 'equipment', label: 'Equipment' },
  { id: 'venues', label: 'Venues' },
  { id: 'safety', label: 'Safety' },
  { id: 'other', label: 'Other' },
];

const apps = [
  { id: 'my-registrations', category: 'registration', label: 'My Registrations', description: 'View your registration status and event details', path: '/my-registrations', icon: '🎟️', roles: [] },
  { id: 'event-registration', category: 'registration', label: 'Event Registration', description: 'Browse events and register or join a waiting list', path: '/event-registration', icon: '📅', roles: [] },
  { id: 'reserved-equipment', category: 'equipment', label: 'Reserved Equipment', description: 'Reserve equipment for event requests and manage reservations', path: '/reserved-equipment', icon: '???', roles: [] },
  {
    id: 'venue-bookings', category: 'venues',
    label: 'Venue Bookings',
    // A request now starts from the event being planned, so this tile is for
    // following the requests already made and the decisions on them.
    description: 'Track your venue booking requests and their outcomes',
    path: '/venue-bookings',
    icon: '📋',
    roles: [],
  },
  {
    id: 'review-venue-bookings', category: 'venues',
    label: 'Review Venue Bookings',
    description: 'Approve or reject venue booking requests',
    path: '/review-venue-bookings',
    icon: '🗂️',
    roles: [],
  },
  {
    id: 'equipment', category: 'equipment',
    label: 'Review Equipment Requests',
    description: 'Review equipment requests after reserving the full quantity',
    path: '/equipment',
    icon: '🛠️',
    roles: [],
  },
  {
    id: 'equipment-requests', category: 'equipment',
    label: 'Request Equipment',
    description: 'Request equipment for your events and track the decisions',
    path: '/equipment-requests',
    icon: '🎛️',
    roles: [],
  },
  {
    id: 'events', category: 'events',
    label: 'Events',
    description: 'Open Events',
    path: '/events',
    icon: '📅',
    roles: [],
  },

  {
    id: 'event-change-requests', category: 'events',
    label: 'Request Event Changes',
    description: 'Propose changes to an event you submitted',
    path: '/event-change-requests/new',
    icon: '📝',
    roles: [],
  },
  {
    id: 'review-event-requests', category: 'events',
    label: 'Review Event Requests',
    description: 'Open Review Event Requests',
    path: '/review-event-requests',
    icon: '📋',
    roles: [],
  },
  {
    id: 'review-event-change-requests', category: 'events',
    label: 'Review Event Changes',
    description: 'Review requested changes for events assigned to you',
    path: '/review-event-change-requests',
    icon: '📋',
    roles: [],
  },
  {
    id: 'assign-event-coordinators', category: 'events',
    label: 'Assign Event Coordinators',
    description: 'Assign unassigned event requests to Event Coordinators',
    path: '/assign-event-coordinators',
    icon: '👥',
    roles: ['Event Coordinator Lead'],
  },
  {
    id: 'reassign-event-coordinators', category: 'events',
    label: 'Reassign Event Coordinators',
    description: 'View event stages and reassign Event Coordinators',
    path: '/reassign-event-coordinators',
    icon: '📊',
    roles: ['Event Coordinator Lead'],
  },
  {
    id: 'equipment-availability', category: 'equipment',
    label: 'Check Equipment Availability',
    description: 'Open Equipment Availability',
    path: '/equipment-availability',
    icon: '🧰',
    roles: [],
  },
  {
    id: 'venue-management', category: 'venues',
    label: 'Venue Management',
    description: 'View and manage the venue catalogue',
    path: '/venues',
    icon: '🏛️',
    roles: [],
  },
  {
    id: 'venue-search', category: 'venues',
    label: 'Venue Search',
    description: 'Open Venue Search',
    path: '/venue-search',
    icon: '🏢',
    roles: [],
  },
  {
    id: 'operational-safety-reviews', category: 'safety',
    label: 'Safety Reviews',
    description: 'Review operational safety arrangements for planned events',
    path: '/operational-safety-reviews',
    icon: '✅',
    roles: ['Safety Officer'],
  },
];

export const HOME_APPS = apps.map(app => ({ ...app, category: app.category || 'other', roles: rolesForPath(app.path) }));
