// The access token is a Supabase JWT; its "sub" claim is the signed-in user's id.
export const userId = (token) => JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub;

// "under_review" -> "Under review", "sound_system" -> "Sound system".
export const humanise = (value) => value.charAt(0).toUpperCase() + value.slice(1).replace('_', ' ');

export async function api(path, token, { method = 'GET', body } = {}) {
  const response = await fetch('/api/event-requests' + path, {
    method, cache: 'no-store', body: body && JSON.stringify(body),
    headers: { Authorization: 'Bearer ' + token, ...(body && { 'Content-Type': 'application/json' }) },
  });
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.error || 'Something went wrong. Please try again.'), { details: data.errors });
  return data;
}
