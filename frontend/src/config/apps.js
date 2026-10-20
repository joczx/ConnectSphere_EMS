import { rolesForPath } from '../auth/access';

/**
 * Home-page app definition shape:
 * {
 *   id: string,
 *   label: string,
 *   description: string,
 *   path: string,
 *   icon: string,
 *   roles: string[]
 * }
 */
const apps = [
  { id: 'reserved-equipment', label: 'Reserved Equipment', description: 'Reserve equipment for event requests and manage reservations', path: '/reserved-equipment', icon: '???', roles: [] },
  {
    id: 'venue-bookings',
    label: 'Venue Bookings',
    // A request now starts from the event being planned, so this tile is for
    // following the requests already made and the decisions on them.
    description: 'Track your venue booking requests and their outcomes',
    path: '/venue-bookings',
    icon: '📋',
    roles: [],
  },
  {
    id: 'review-venue-bookings',
    label: 'Review Venue Bookings',
    description: 'Approve or reject venue booking requests',
    path: '/review-venue-bookings',
    icon: '🗂️',
    roles: [],
  },
  {
    id: 'equipment',
    label: 'Equipment Requests',
    description: 'Review equipment requests after reserving the full quantity',
    path: '/equipment',
    icon: '🛠️',
    roles: [],
  },
  {
    id: 'equipment-requests',
    label: 'Request Equipment',
    description: 'Request equipment for your events and track the decisions',
    path: '/equipment-requests',
    icon: '🎛️',
    roles: [],
  },
  {
    id: 'events',
    label: 'Events',
    description: 'Open Events',
    path: '/events',
    icon: '📅',
    roles: [],
  },
  {
    id: 'event-requests',
    label: 'Event Requests',
    description: 'Open Event Requests',
    path: '/event-requests',
    icon: '📝',
    roles: [],
  },
  {
    id: 'event-change-requests',
    label: 'Request Event Changes',
    description: 'Propose changes to an event you submitted',
    path: '/event-change-requests/new',
    icon: '📝',
    roles: [],
  },
  {
    id: 'review-event-requests',
    label: 'Review Event Requests',
    description: 'Open Review Event Requests',
    path: '/review-event-requests',
    icon: '📋',
    roles: [],
  },
  {
    id: 'review-event-change-requests',
    label: 'Review Event Changes',
    description: 'Review requested changes for events assigned to you',
    path: '/review-event-change-requests',
    icon: '📋',
    roles: [],
  },
  {
    id: 'assign-event-coordinators',
    label: 'Assign Event Coordinators',
    description: 'Assign unassigned event requests to Event Coordinators',
    path: '/assign-event-coordinators',
    icon: '👥',
    roles: ['Event Coordinator Lead'],
  },
  {
    id: 'reassign-event-coordinators',
    label: 'Reassign Event Coordinators',
    description: 'View event stages and reassign Event Coordinators',
    path: '/reassign-event-coordinators',
    icon: '📊',
    roles: ['Event Coordinator Lead'],
  },
  {
    id: 'equipment-availability',
    label: 'Check Equipment Availability',
    description: 'Open Equipment Availability',
    path: '/equipment-availability',
    icon: '🧰',
    roles: [],
  },
  {
    id: 'venue-management',
    label: 'Venue Management',
    description: 'View and manage the venue catalogue',
    path: '/venues',
    icon: '🏛️',
    roles: [],
  },
  {
    id: 'venue-search',
    label: 'Venue Search',
    description: 'Open Venue Search',
    path: '/venue-search',
    icon: '🏢',
    roles: [],
  },
  {
    id: 'venue-suitability',
    label: 'Venue Suitability',
    description: 'Check venue suitability for an event',
    path: '/venue-suitability',
    icon: '✅',
    roles: [],
  },
  {
    id: 'operational-safety-reviews',
    label: 'Safety Reviews',
    description: 'Review operational safety arrangements for planned events',
    path: '/operational-safety-reviews',
    icon: '✅',
    roles: ['Safety Officer'],
  },
];

export const HOME_APPS = apps.map(app => ({ ...app, roles: rolesForPath(app.path) }));
