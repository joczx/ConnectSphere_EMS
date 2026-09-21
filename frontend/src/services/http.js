export async function readApiResponse(response) {
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`The service returned an unexpected response (HTTP ${response.status}). Please try again or contact support.`);
  }
  if (!response.ok) {
    throw Object.assign(new Error(data.error || 'Unable to load data. Please try again.'), { details: data.errors });
  }
  return data;
}
