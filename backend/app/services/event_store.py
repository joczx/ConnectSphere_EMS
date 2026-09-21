"""Query Supabase with user credentials so row-level security enforces access."""
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from flask import request

logger = logging.getLogger(__name__)


class StoreError(Exception):
    def __init__(self, status, message=None, code=None):
        self.code = code
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
        raise StoreError(503, 'Supabase credentials are missing or incomplete. Set SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env.')
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
        code = detail = None
        if error_body:
            try:
                upstream = json.loads(error_body.decode('utf-8'))
                if isinstance(upstream, dict):
                    detail = upstream.get('message')
                    code = upstream.get('code')
            except json.JSONDecodeError:
                pass
        # Upstream wording can name tables, columns and keys, so it is logged
        # for developers rather than carried in the error the caller sees.
        logger.warning('Supabase %s failed for %s: %s', exc.code, path, detail or exc.reason)
        raise StoreError(401 if exc.code in (400, 401, 403) else 503, code=code) from exc
    except (URLError, TimeoutError) as exc:
        raise StoreError(503, 'Supabase is temporarily unavailable.') from exc


def authenticated_token(query=None):
    """Return the caller's verified access token.

    `query` lets a blueprint pass its own supabase_request, so a test that
    patches that module's function also intercepts this user lookup.
    """
    query = query or supabase_request
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        raise StoreError(401)
    user = query('/auth/v1/user', token=token)
    if not user.get('id'):
        raise StoreError(401)
    return token
