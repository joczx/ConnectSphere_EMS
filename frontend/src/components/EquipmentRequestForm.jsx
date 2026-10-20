import { useEffect, useState } from 'react';
import RequiredIndicator from './RequiredIndicator';
import { useAuth } from '../auth/AuthContext';

const EMPTY = { equipment_type: '', quantity: 1, technical_requirements: '' };

// One equipment request for one event: a new one, or changes to `request`
// while it is still pending. Shared by the event page and the Request
// Equipment page so the two cannot drift apart.
export default function EquipmentRequestForm({ eventId, request, onSubmitted, onCancel }) {
  const { api } = useAuth();
  const editing = !!request;
  const [form, setForm] = useState(() => editing ? {
    equipment_type: request.equipment_type || '',
    quantity: request.quantity ?? 1,
    technical_requirements: request.technical_requirements || '',
  } : EMPTY);
  const [equipmentTypes, setEquipmentTypes] = useState([]);
  const [status, setStatus] = useState({ message: '', error: '', busy: false });

  useEffect(() => {
    let ignore = false;
    api('/api/equipment-types', { cache: 'no-store' })
      .then(data => { if (!ignore) setEquipmentTypes(data.equipment_types || []); })
      .catch(err => { if (!ignore) setStatus({ message: '', error: err.message, busy: false }); });
    return () => { ignore = true; };
  }, [api]);

  // A request may name a type no longer in stock; keep it selectable.
  const typeOptions = form.equipment_type && !equipmentTypes.includes(form.equipment_type)
    ? [form.equipment_type, ...equipmentTypes] : equipmentTypes;

  async function submit(event) {
    event.preventDefault();
    setStatus({ message: '', error: '', busy: true });
    const base = `/api/events/${encodeURIComponent(eventId)}/equipment-requests`;
    try {
      const data = await api(editing ? `${base}/${encodeURIComponent(request.equipment_request_id)}` : base, {
        method: editing ? 'PATCH' : 'POST',
        body: {
          equipment_type: form.equipment_type,
          quantity: Number(form.quantity),
          technical_requirements: form.technical_requirements,
        },
      });
      if (editing) {
        setStatus({ message: '', error: '', busy: false });
      } else {
        setStatus({ message: data.message || 'Equipment request submitted successfully.', error: '', busy: false });
        setForm(EMPTY);
      }
      onSubmitted?.(data);
    } catch (err) {
      setStatus({ message: '', error: err.message || 'Unable to save equipment request.', busy: false });
    }
  }

  return <>
    {status.error && <div className="error">{status.error}</div>}
    {status.message && <div className="success">{status.message}</div>}
    <form onSubmit={submit} className="event-equipment-form">
      <h3>{editing ? 'Edit equipment request' : 'New equipment request'}</h3>
      <label>
        Equipment Type
        <RequiredIndicator /><select value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} required>
          <option value="">Select</option>
          {typeOptions.map(type => <option key={type} value={type}>{type}</option>)}
        </select>
      </label>
      <label>
        Quantity
        <RequiredIndicator /><input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required />
      </label>
      <label>
        Technical requirements
        <textarea value={form.technical_requirements} onChange={(e) => setForm({ ...form, technical_requirements: e.target.value })} rows="6" />
      </label>
      <div>
        <button type="submit" disabled={status.busy}>{editing ? 'Save changes' : 'Submit equipment request'}</button>
        {onCancel && <button type="button" className="secondary" disabled={status.busy} onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  </>;
}
