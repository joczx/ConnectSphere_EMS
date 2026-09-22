const labels = {
  pending: 'Pending review', accepted: 'Accepted', rejected: 'Rejected',
  partially_accepted: 'Partially accepted', in_progress: 'In progress', completed: 'Completed',
};

export default function EquipmentRequestStatus({ request }) {
  const accepted = request.accepted_quantity ?? (
    ['accepted', 'partially_accepted', 'in_progress', 'completed'].includes(request.status) ? request.quantity : null
  );
  return <>
    <p>Status: {labels[request.status] || request.status || 'Pending review'}</p>
    <p>Requested quantity: {request.quantity}</p>
    {accepted !== null && <p>Accepted quantity: {accepted}</p>}
    {request.reason_for_rejection && <p>Reason: {request.reason_for_rejection}</p>}
  </>;
}
