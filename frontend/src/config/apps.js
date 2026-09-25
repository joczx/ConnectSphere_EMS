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
    id: 'equipment',
    label: 'Reserve Equipment',
    description: 'Review equipment requests and accept or reject reservations',
    path: '/equipment',
    icon: '🛠️',
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
];
