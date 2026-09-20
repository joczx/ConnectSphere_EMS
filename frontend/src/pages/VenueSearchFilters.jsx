import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';

const FACILITIES = [
  ['stage', 'Stage'],
  ['projector', 'Projector'],
  ['sound_system', 'Sound system'],
  ['video_conferencing', 'Video conferencing'],
  ['wifi', 'Wi-Fi'],
  ['parking', 'Parking'],
  ['catering_area', 'Catering area'],
  ['air_conditioning', 'Air conditioning'],
];

export default function VenueSearchFilters({ onSignOut }) {
  const navigate = useNavigate();

  function showResults(event) {
    event.preventDefault();
    // TODO: Preserve the filter values in the URL and call the venue-search API.
    navigate('/venue-search');
  }

  return (
    <>
      <Navbar onSignOut={onSignOut} />
      <main className="container">
        <Link to="/venue-search">← Back to venue search</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE SEARCH</p>
            <h1>Filter conditions</h1>
          </div>
        </div>
        <p>Enter the event requirements used to search for possible venues.</p>

        <form className="panel search-filter-form" onSubmit={showResults}>
          <fieldset>
            <legend>Event timing</legend>
            <div className="search-filter-grid">
              <label>
                Event date
                <input name="date" type="date" />
              </label>
              <label>
                Start time
                <input name="start_time" type="time" />
              </label>
              <label>
                End time
                <input name="end_time" type="time" />
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Venue requirements</legend>
            <div className="search-filter-grid">
              <label>
                Expected attendance
                <input name="capacity" type="number" min="1" placeholder="Number of attendees" />
              </label>
              <label>
                Location
                <input name="location" type="search" placeholder="Venue, building, street or postal code" />
              </label>
              <label>
                Room layout
                <select name="layout" defaultValue="">
                  <option value="">Any layout</option>
                  <option value="theatre">Theatre</option>
                  <option value="classroom">Classroom</option>
                  <option value="boardroom">Boardroom</option>
                  <option value="banquet">Banquet</option>
                  <option value="exhibition">Exhibition</option>
                  <option value="u_shape">U-shape</option>
                  <option value="cabaret">Cabaret</option>
                </select>
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Accessibility</legend>
            <div className="search-filter-grid">
              <label>
                Wheelchair accessibility
                <select name="wheelchair_accessible" defaultValue="">
                  <option value="">Any</option>
                  <option value="true">Required</option>
                </select>
              </label>
              <label>
                Blind accessibility
                <select name="blind_accessible" defaultValue="">
                  <option value="">Any</option>
                  <option value="true">Required</option>
                </select>
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Required facilities</legend>
            <div className="facility-options">
              {FACILITIES.map(([value, label]) => (
                <label className="facility-option" key={value}>
                  <input name="facilities" type="checkbox" value={value} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="search-filter-actions">
            <button type="submit">Search venues</button>
            <button type="reset" className="secondary">Clear all</button>
          </div>
        </form>
      </main>
    </>
  );
}
