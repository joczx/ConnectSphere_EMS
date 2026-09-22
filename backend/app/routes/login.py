import re

from flask import Blueprint, jsonify, request

from app.services.event_store import StoreError, supabase_request

login_bp = Blueprint('login', __name__, url_prefix='/api')


@login_bp.errorhandler(StoreError)
def handle_store_error(error):
    return jsonify(error.to_dict()), error.status


def session_response(result):
    return jsonify(
        access_token=result['access_token'], refresh_token=result['refresh_token']
    )


@login_bp.post('/login')
def login():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not isinstance(body.get('email'), str) or not isinstance(body.get('password'), str):
        return jsonify(error='Email and password are required.'), 400

    email = body['email'].strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return jsonify(error='Invalid email address. Please enter a valid email address.'), 400
    if not body['password']:
        return jsonify(error='Please enter your password.'), 400

    try:
        result = supabase_request('/auth/v1/token?grant_type=password', payload={
            'email': email, 'password': body['password'],
        })
    except StoreError as error:
        if error.status == 401:
            return jsonify(error='Incorrect email or password. Please try again.'), 401
        raise
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
