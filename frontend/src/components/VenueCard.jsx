import { Link } from 'react-router-dom';

function readable(value) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function address(venue) {
  return [
    venue.unit_number,
    venue.building_name,
    [venue.block_number, venue.street_name].filter(Boolean).join(' '),
    venue.postal_code,
  ].filter(Boolean).join(', ');
}

export default function VenueCard({ venue }) {
  const characteristics = [...(venue.facilities || []), ...(venue.supported_room_layouts || [])];

  return (
    <Link className="panel venue-card" to={`/venues/${venue.venue_id}`}>
      <h3>{venue.venue_name}</h3>
      <p>{address(venue) || 'Address not specified'}</p>
      <p className="metadata">
        Capacity: {Number.isFinite(venue.capacity) ? venue.capacity.toLocaleString() : 'Not specified'}
      </p>
      <div className="venue-card-tags" aria-label="Venue characteristics">
        {venue.wheelchair_accessible && <span>Wheelchair accessible</span>}
        {venue.blind_accessible && <span>Blind accessible</span>}
        {characteristics.slice(0, 4).map(value => <span key={value}>{readable(value)}</span>)}
        {characteristics.length > 4 && <span>+{characteristics.length - 4} more</span>}
      </div>
      <span className="venue-card-link">View venue information →</span>
    </Link>
  );
}
