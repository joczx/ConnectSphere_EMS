function person(request, role) {
  return request[role]?.name?.trim() || request[role + '_id'] || '-';
}

export default function EventRequestPeople({ request }) {
  return <div className="metadata">
    <p>Event Organiser: {person(request, 'event_organiser')}</p>
    <p>Event Coordinator: {person(request, 'event_coordinator')}</p>
  </div>;
}
