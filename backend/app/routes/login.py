from flask import Blueprint, jsonify, request

from app.services.event_store import supabase_request

login_bp = Blueprint('login', __name__, url_prefix='/api')


def session_response(result):
    return jsonify(
        access_token=result['access_token'], refresh_token=result['refresh_token']
    )


@login_bp.post('/login')
def login():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not isinstance(body.get('email'), str) or not isinstance(body.get('password'), str):
        return jsonify(error='Email and password are required.'), 400

    result = supabase_request('/auth/v1/token?grant_type=password', payload={
        'email': body['email'], 'password': body['password'],
    })
    return session_response(result)


@login_bp.post('/refresh')
def refresh():
    body = request.get_json(silent=True) or {}
    refresh_token = body.get('refresh_token') if isinstance(body, dict) else None
    if not isinstance(refresh_token, str) or not refresh_token:
        return jsonify(error='Refresh token is required.'), 400
    result = supabase_request('/auth/v1/token?grant_type=refresh_token', payload={
        'refresh_token': refresh_token,
    })
    return session_response(result)
