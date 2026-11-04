import { test, expect, notifications } from './story-fixtures.js';

// SCRUM-265 AC1-4: submission to organiser/coordinator and decision to organiser.
for (const decision of ['approve', 'reject']) {
  test(`SCRUM-265: ${decision}d change request has actionable notifications`, async ({ page, story }) => {
    const event = await story.event(); const change = await story.change(event);
    await notifications(page, 'Event Organiser', event.event_name, 'Event change request submitted');
    const coordinator = await notifications(page, 'Event Coordinator', event.event_name, 'New event change request');
    await expect(coordinator).toContainText(/attendance|capacity/i);
    await story.call('Event Coordinator', 'POST', `/api/event-change-requests/${change.event_change_request_id}/decision`, { decision, reason: story.prefix + ' decision' });
    const result = await notifications(page, 'Event Organiser', event.event_name, decision === 'approve' ? 'Event change request approved' : 'Event change request rejected');
    await result.getByRole('button').click();
    await expect(page.getByRole('main')).toContainText(event.event_name);
  });
}
