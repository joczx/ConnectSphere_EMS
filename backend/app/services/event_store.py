"""Query Supabase with user credentials so row-level security enforces access."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class StoreError(Exception):
    def __init__(self, status):
        self.status = status


def supabase_request(path, token=None, payload=None):
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    if not base or not key:
        raise StoreError(503)
    headers = {'apikey': key, 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = Request(base + path, headers=headers,
                  data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urlopen(req, timeout=10) as response:
            return json.load(response)
    except HTTPError as exc:
        raise StoreError(401 if exc.code in (400, 401, 403) else 503) from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise StoreError(503) from exc
