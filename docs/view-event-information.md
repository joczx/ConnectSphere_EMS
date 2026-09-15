# View Event Information

This story adds sign-in, an authorised event list and a read-only event detail page.
Access is granted explicitly per event to Event Organisers and Event Coordinators
through `event_members`. Membership is managed by trusted administrators; users
cannot grant themselves access. Sharing access across an entire client organisation
is not assumed.

## Setup

1. Apply `supabase/002_create_events.sql` in your Supabase SQL editor after migration 001.
2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `backend/.env`. Use the public anon
   key, never a service-role key. Credentials are only configured on the backend.
3. Create email/password users in Supabase Auth. Through trusted admin tooling,
   insert event records and corresponding `event_members` rows with each Auth user ID
   and role `event_organiser` or `event_coordinator`.
4. Start Flask with `python run.py` from `backend`, and run `npm install` then
   `npm run dev` from `frontend`. Vite proxies `/api` to Flask on port 5000.
   Production hosting must also route `/api` to Flask over HTTPS.
5. Sign in using the provisioned account. No demo credentials or events are bundled.

The detail view displays every field in the story, marking missing information as
“Not specified” and hiding registration details when registration is not required.
Dates are shown in Singapore time. Database updates increment the version and stamp
the update time. Reads are uncached; the UI refreshes on navigation, window focus,
every minute, and using Refresh. Sessions expire according to Supabase Auth settings;
users sign in again after expiry.

## Verification

Run `python -m unittest discover -s tests -v` from `backend` and `npm run build`
from `frontend`. API tests mock Supabase; they do not validate deployed RLS policies.

For integration verification, provision two users with different event memberships.
Confirm each sees only their assigned events and receives 404 when requesting the
other event directly. Check the same isolation through Supabase REST with each
user's token. Update an event through trusted admin tooling and confirm Refresh
displays the new information, version, and timestamp. Remove membership and confirm
the next refresh no longer displays the event. Verify optional fields, zero attendance,
expired sessions, and a narrow mobile viewport.

Editing and impact assessment belong to separate user stories and have no UI or
write API in this implementation.
