// The access token is a Supabase JWT; its "sub" claim is the signed-in user's id.
export const userId = (token) => JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub;

// "under_review" -> "Under review", "sound_system" -> "Sound system".
export const humanise = (value) => value.charAt(0).toUpperCase() + value.slice(1).replace('_', ' ');

export const eventRequestsApi = (api, path, options) => (
  api('/api/event-requests' + path, { cache: 'no-store', ...options })
);
