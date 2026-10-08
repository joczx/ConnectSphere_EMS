export async function readApiResponse(response) {
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw Object.assign(
      new Error(`The service returned an unexpected response (HTTP ${response.status}). Please try again or contact support.`),
      { status: response.status },
    );
  }
  if (!response.ok) {
    // The status travels with the error, so a page can tell "you may not see
    // this" (403) apart from a real failure and treat it as nothing to show.
    throw Object.assign(new Error(data.error || 'Unable to load data. Please try again.'), {
      details: data.errors, data, status: response.status,
    });
  }
  return data;
}
