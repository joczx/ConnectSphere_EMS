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
    description: 'Check availability and reserve equipment for an event',
    path: '/equipment',
    icon: '🛠️',
    roles: [],
  },
  {
    id: 'events',
    label: 'Events',
    description: 'Open Events',
    path: '/home',
    icon: '📅',
    roles: [],
  },
  {
    id: 'event-requests',
    label: 'Event Requests',
    description: 'Open Event Requests',
    path: '/home',
    icon: '📝',
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
