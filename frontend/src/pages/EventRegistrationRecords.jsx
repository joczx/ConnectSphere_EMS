import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EventRegistrationRoster from '../components/EventRegistrationRoster';

export default function EventRegistrationRecords() {
  const { eventId } = useParams();
  return <><Navbar /><main className="container event-reference-workspace">
    <Link to={`/events/${encodeURIComponent(eventId)}`}>Back to event</Link>
    <div className="heading"><div><p className="eyebrow">EVENT REGISTRATION</p><h1>Registration records</h1></div></div>
    <p className="event-page-description">View attendee contact details and current registration statuses for this event.</p>
    <EventRegistrationRoster key={eventId} eventId={eventId} />
  </main></>;
}
