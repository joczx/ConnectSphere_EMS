import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readApiResponse } from '../src/services/http.js';

test('successful deletion accepts HTTP 204 without a JSON body', async () => {
  assert.equal(await readApiResponse(new Response(null, { status: 204 })), null);
});

test('JSON success responses are still returned', async () => {
  assert.deepEqual(await readApiResponse(new Response('{"event":{"event_id":1}}')),
    { event: { event_id: 1 } });
});

test('JSON errors preserve status and field errors', async () => {
  await assert.rejects(readApiResponse(new Response(JSON.stringify({ error: 'Cannot delete this request.',
    errors: { status: 'Only drafts can be deleted.' } }), { status: 409 })), error => {
    assert.equal(error.status, 409);
    assert.equal(error.message, 'Cannot delete this request.');
    assert.deepEqual(error.details, { status: 'Only drafts can be deleted.' });
    return true;
  });
});

test('unexpected empty or non-JSON responses still produce an error', async () => {
  for (const response of [new Response(''), new Response('Service unavailable', { status: 503 })]) {
    await assert.rejects(readApiResponse(response), /unexpected response/);
  }
});
