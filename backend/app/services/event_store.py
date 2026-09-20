"""Query Supabase with user credentials so row-level security enforces access."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from flask import request


class StoreError(Exception):
    def __init__(self, status, message=None):
        self.status = status
        self.message = message or (
            'Please sign in again.' if status == 401 else 'Event service is temporarily unavailable.'
        )

    def to_dict(self):
        return {'error': self.message}


def supabase_request(path, token=None, payload=None):
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    if not base or not key:
        raise StoreError(503, 'Supabase credentials are missing or incomplete. Set SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_KEY) in backend/.env.')
    headers = {'apikey': key, 'Content-Type': 'application/json'}
    if payload is not None:
        headers['Prefer'] = 'return=representation'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = Request(base + path, headers=headers,
                  data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urlopen(req, timeout=10) as response:
            body = response.read()
            if not body:
                return []
            try:
                return json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as exc:
                snippet = body[:200].decode('utf-8', 'replace')
                raise StoreError(503, f'Supabase returned a non-JSON response. Check the project URL and API key. Raw response: {snippet}') from exc
    except HTTPError as exc:
        error_body = exc.read()
        if error_body:
            try:
                payload = json.loads(error_body.decode('utf-8'))
                message = payload.get('message') if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                message = None
            raise StoreError(401 if exc.code in (400, 401, 403) else 503, message or exc.reason or 'Supabase request failed.') from exc
        raise StoreError(401 if exc.code in (400, 401, 403) else 503, exc.reason or 'Supabase request failed.') from exc
    except (URLError, TimeoutError) as exc:
        raise StoreError(503, 'Supabase is temporarily unavailable.') from exc


def authenticated_token():
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise StoreError(401)
    user = supabase_request('/auth/v1/user', token=token)
    if not user.get('id'):
        raise StoreError(401)
    return token
