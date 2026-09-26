import { Link } from 'react-router-dom';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function VenueForm({ mode, venueId }) {
  const isUpdate = mode === 'update';
  const cancelPath = isUpdate ? `/venues/${venueId}` : '/venues';

  return (
    <form className="panel venue-form" onSubmit={(event) => event.preventDefault()}>
      <p className="skeleton-note" role="note">
        This form is a frontend skeleton. Saving will be connected to the venue API in a later step.
      </p>

      <fieldset>
        <legend>Venue information</legend>
        <div className="venue-form-grid">
          <label>
            Venue name
            <input name="venue_name" required placeholder="Enter venue name" />
          </label>
          <label>
            Capacity
            <input name="capacity" type="number" min="1" required placeholder="Maximum number of people" />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Address</legend>
        <div className="venue-form-grid">
          <label>
            Postal code
            <input name="postal_code" inputMode="numeric" maxLength="6" required placeholder="6-digit postal code" />
          </label>
          <label>
            Block number
            <input name="block_number" required placeholder="Block number" />
          </label>
          <label>
            Street name
            <input name="street_name" required placeholder="Street name" />
          </label>
          <label>
            Building name <span className="metadata">(optional)</span>
            <input name="building_name" placeholder="Building name" />
          </label>
          <label>
            Unit number <span className="metadata">(optional)</span>
            <input name="unit_number" placeholder="Unit or level" />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Accessibility</legend>
        <div className="venue-choice-row">
          <label className="venue-checkbox"><input name="wheelchair_accessible" type="checkbox" /> Wheelchair accessible</label>
          <label className="venue-checkbox"><input name="blind_accessible" type="checkbox" /> Blind accessible</label>
        </div>
        <label>
          Accessibility notes <span className="metadata">(optional)</span>
          <textarea name="accessibility_notes" rows="4" placeholder="Describe accessibility support or limitations" />
        </label>
      </fieldset>

      <fieldset>
        <legend>Venue characteristics</legend>
        <div className="venue-form-grid">
          <label>
            Facilities
            <textarea name="facilities" rows="4" required placeholder="Facility choices will be added here" />
          </label>
          <label>
            Supported room layouts
            <textarea name="supported_room_layouts" rows="4" required placeholder="Room layout choices will be added here" />
          </label>
          <label>
            Default setup time (minutes)
            <input name="default_setup_minutes" type="number" min="0" required placeholder="0" />
          </label>
          <label>
            Default turnaround time (minutes)
            <input name="default_turnaround_minutes" type="number" min="0" required placeholder="0" />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Operating hours</legend>
        <div className="operating-hours-skeleton">
          {DAYS.map((day) => (
            <div className="operating-hours-row" key={day}>
              <strong>{day}</strong>
              <label><span className="sr-only">{day} opening time</span><input type="time" aria-label={`${day} opening time`} /></label>
              <span aria-hidden="true">to</span>
              <label><span className="sr-only">{day} closing time</span><input type="time" aria-label={`${day} closing time`} /></label>
              <label className="venue-checkbox"><input type="checkbox" /> Closed</label>
            </div>
          ))}
        </div>
      </fieldset>

      <div className="venue-page-actions">
        <button type="submit" disabled>{isUpdate ? 'Update venue' : 'Create venue'}</button>
        {isUpdate && <button type="button" className="secondary" disabled>Save draft</button>}
        <Link className="button-link secondary-link" to={cancelPath}>Cancel</Link>
      </div>
    </form>
  );
}
