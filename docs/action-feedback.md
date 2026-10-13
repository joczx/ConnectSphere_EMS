# Shared action popups

Every role uses the same feedback provider. Success notifications dismiss after
six seconds; error notifications remain until dismissed. Confirmation dialogs
use native modal dialogs with keyboard focus management, Escape to go back,
and explicit action labels. Destructive confirmations focus the safe button.

Authenticated API writes automatically show the backend result message, or an
action-specific fallback. Final failures show an error popup and still throw
the original error so pages can display field details. Session refresh/retry
continues to happen inside AuthContext; only the final result is announced.

Routine GET requests and automated status refreshes are quiet. A user-driven
search may opt in with `feedback: true` and `successMessage`, which accepts text
or a function of the result. Use `successFeedback: false` for an intermediate
write in a multi-step action; errors still display. `feedback: false` suppresses
both success and error announcements and is reserved for background work.

For local actions and validation:

```jsx
const { notify, confirm } = useFeedback();
notify('Your draft has been saved on this device.', 'success', 'Draft saved');
notify('Choose a positive whole quantity.', 'error', 'Check quantity');
if (!(await confirm('Cancel this event?', {
  title: 'Cancel event', confirmLabel: 'Cancel event', destructive: true,
}))) return;
```

The provider catches native form validation events. Feature-specific validation
also calls `notify`; inline field errors stay available for correction. Login,
logout, local draft saving, searches, review decisions, critical changes,
reservations, cancellations, venue deletion and API saves use this shared UI.
Normal navigation and choosing individual field values do not need popups.

Verify the message selection and notification policy from the repo root:

```powershell
node --test frontend/tests/action-feedback.test.mjs
cd frontend
npm run build
```

The in-memory React tests exercise popup dismissal, confirmation choices,
validation, permission errors, and session refresh without sending live API
requests. From the repository root:

```powershell
npm install --prefix frontend/node_modules/.feedback-qa jsdom --no-save --package-lock=false
node --test frontend/tests/feedback-interactions.test.mjs
```

Native dialog appearance and browser focus trapping still require a connected
browser for visual verification.
