import { useEffect, useRef, useState } from 'react';
import RequiredIndicator from './RequiredIndicator';
import { FACILITIES, label } from '../services/eventFields';

export default function RequiredFacilitiesPicker({ initialItems }) {
  const [selected, setSelected] = useState(() => initialItems?.length === 0 ? ['none'] : initialItems || []);
  const validationInput = useRef(null);
  useEffect(() => {
    validationInput.current?.setCustomValidity(selected.length ? '' : 'Select a facility or choose No facilities needed.');
  }, [selected]);
  function toggle(facility, checked) {
    setSelected(current => facility === 'none' ? checked ? ['none'] : []
      : checked ? [...current.filter(item => item !== 'none'), facility] : current.filter(item => item !== facility));
  }
  return <fieldset className="facilities-picker">
    <legend>Required facilities<RequiredIndicator /></legend>
    <p className="metadata">Select all facilities your event needs.</p>
    <div className="facilities-picker-options">
      {FACILITIES.map(facility => <label className={'facility-choice' + (selected.includes(facility) ? ' is-selected' : '')} key={facility}>
        <input type="checkbox" name="required_facilities" value={facility} checked={selected.includes(facility)}
          onChange={event => toggle(facility, event.target.checked)} />
        <span>{label(facility)}</span>
      </label>)}
    </div>
    <label className="facilities-none requirements-none"><input ref={validationInput} type="checkbox" name="required_facilities" value="none" checked={selected.includes('none')}
      onChange={event => toggle('none', event.target.checked)} />No facilities needed</label>
  </fieldset>;
}
