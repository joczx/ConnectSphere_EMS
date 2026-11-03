import { useRef, useState } from 'react';
import { EQUIPMENT_TYPES } from '../config/equipmentTypes';

const canonicalType = value => EQUIPMENT_TYPES.find(type => type.toLowerCase() === value?.toLowerCase()) || value || '';

export default function EquipmentRequirementsPicker({ initialItems }) {
  const [none, setNone] = useState(Array.isArray(initialItems) && initialItems.length === 0);
  const [rows, setRows] = useState(() => initialItems?.length
    ? initialItems.map((item, index) => ({ ...item, equipment_type: canonicalType(item.equipment_type), key: index }))
    : [{ key: 0, equipment_type: '', quantity: 1 }]);
  const nextKey = useRef(rows.length);
  const selected = rows.filter(item => item.equipment_type);
  const payload = none ? [] : selected.length ? selected.map(item => ({
    equipment_type: item.equipment_type, quantity: item.quantity === '' ? null : Number(item.quantity), notes: item.notes || null,
  })) : null;
  const change = (key, field, value) => setRows(current => current.map(item => item.key === key ? { ...item, [field]: value } : item));

  return <div className="equipment-requirements-picker">
    <div className="equipment-picker-heading">
      <div><p className="equipment-picker-title">Equipment requirements</p>
        <p className="metadata">Choose a type and enter the quantity you need.</p></div>
    </div>
    <input type="hidden" name="equipment_requirements" value={payload === null ? '' : JSON.stringify(payload)} />
    <div className="equipment-picker-body"><fieldset disabled={none}>
      <div className="equipment-picker-columns" aria-hidden="true"><span>Equipment type</span><span>Quantity</span><span /></div>
      {rows.map((item, index) => {
        const options = EQUIPMENT_TYPES.includes(item.equipment_type) || !item.equipment_type
          ? EQUIPMENT_TYPES : [item.equipment_type, ...EQUIPMENT_TYPES];
        return <div className="equipment-requirement-row" key={item.key}>
          <label><span className="sr-only">Equipment type {index + 1}</span><select required value={item.equipment_type} onChange={event => change(item.key, 'equipment_type', event.target.value)}>
            <option value="">Select equipment</option>
            {options.map(type => <option key={type} value={type} disabled={rows.some(other => other.key !== item.key && other.equipment_type === type)}>{type}</option>)}
          </select></label>
          <label><span className="sr-only">Quantity {index + 1}</span><input type="number" required min="1" step="1" value={item.quantity} onChange={event => change(item.key, 'quantity', event.target.value)} /></label>
          <button type="button" className="secondary" aria-label={`Remove equipment ${index + 1}`} onClick={() => setRows(current => current.length === 1
            ? [{ key: nextKey.current++, equipment_type: '', quantity: 1 }]
            : current.filter(row => row.key !== item.key))}>Remove</button>
        </div>;
      })}
      <button type="button" className="secondary equipment-picker-add" disabled={selected.length >= EQUIPMENT_TYPES.length || rows.some(item => !item.equipment_type)}
        onClick={() => setRows(current => [...current, { key: nextKey.current++, equipment_type: '', quantity: 1 }])}>Add equipment</button>
    </fieldset>
    <label className="equipment-none requirements-none"><input type="checkbox" checked={none} onChange={event => setNone(event.target.checked)} />No equipment needed</label>
    </div>
  </div>;
}
