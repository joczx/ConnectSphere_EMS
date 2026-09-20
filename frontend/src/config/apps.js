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
export const HOME_APPS = [
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
    id: 'review-event-requests',
    label: 'Review Event Requests',
    description: 'Open Review Event Requests',
    path: '/review-event-requests',
    icon: '📋',
    roles: [],
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
    id: 'venue-search',
    label: 'Venue Search',
    description: 'Open Venue Search',
    path: '/home',
    icon: '🏢',
    roles: [],
  },
];
