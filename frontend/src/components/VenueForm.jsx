import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from './Alert';
import { VENUE_DAYS, VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';

export default function VenueForm({ mode, venueId, onSubmit, submitting = false, errors = {}, error = '' }) {
  const isUpdate = mode === 'update';
  const cancelPath = isUpdate ? `/venues/${venueId}` : '/venues';
  const [closedDays, setClosedDays] = useState({});
  const issues = Object.values(errors);

  return (
    <form className="panel venue-form" onSubmit={onSubmit || ((event) => event.preventDefault())}>
      {isUpdate && <p className="skeleton-note" role="note">Updating venues will be connected in a later step.</p>}
      {(error || issues.length > 0) && <Alert variant="destructive">
        <AlertTitle>Unable to create venue</AlertTitle>
        <AlertDescription>
          {error && <p>{error}</p>}
          {issues.length > 0 && <ul>{issues.map(issue => <li key={issue}>{issue}</li>)}</ul>}
        </AlertDescription>
      </Alert>}

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
            Default setup time (minutes)
            <input name="default_setup_minutes" type="number" min="0" required placeholder="0" />
          </label>
          <label>
            Default turnaround time (minutes)
            <input name="default_turnaround_minutes" type="number" min="0" required placeholder="0" />
          </label>
        </div>
        <div className="layout-options">
          <p className="filter-label">Facilities</p>
          <p className="filter-help">Choose one or more facilities.</p>
          <div className="facility-options">{VENUE_FACILITIES.map(([value, label]) => (
            <label className="facility-option" key={value}><input name="facilities" type="checkbox" value={value} />{label}</label>
          ))}</div>
        </div>
        <div className="layout-options">
          <p className="filter-label">Supported room layouts</p>
          <p className="filter-help">Choose one or more layouts.</p>
          <div className="facility-options">{VENUE_ROOM_LAYOUTS.map(([value, label]) => (
            <label className="facility-option" key={value}><input name="supported_room_layouts" type="checkbox" value={value} />{label}</label>
          ))}</div>
        </div>
      </fieldset>

      <fieldset>
        <legend>Operating hours</legend>
        <div className="operating-hours-skeleton">
          {VENUE_DAYS.map(([day, label]) => (
            <div className="operating-hours-row" key={day}>
              <strong>{label}</strong>
              <label><span className="sr-only">{label} opening time</span><input name={`${day}_open`} type="time" aria-label={`${label} opening time`} required={!closedDays[day]} disabled={closedDays[day]} /></label>
              <span aria-hidden="true">to</span>
              <label><span className="sr-only">{label} closing time</span><input name={`${day}_close`} type="time" aria-label={`${label} closing time`} required={!closedDays[day]} disabled={closedDays[day]} /></label>
              <label className="venue-checkbox"><input name={`${day}_closed`} type="checkbox" checked={Boolean(closedDays[day])} onChange={event => setClosedDays(current => ({ ...current, [day]: event.target.checked }))} /> Closed</label>
            </div>
          ))}
        </div>
      </fieldset>

      <div className="venue-page-actions">
        <button type="submit" disabled={isUpdate || submitting}>{submitting ? 'Creating venue…' : isUpdate ? 'Update venue' : 'Create venue'}</button>
        {isUpdate && <button type="button" className="secondary" disabled>Save draft</button>}
        <Link className="button-link secondary-link" to={cancelPath}>Cancel</Link>
      </div>
    </form>
  );
}
