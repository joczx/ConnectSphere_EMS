from flask import Blueprint, jsonify, request

from app.services.event_store import supabase_request

login_bp = Blueprint('login', __name__, url_prefix='/api')


@login_bp.post('/login')
def login():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not isinstance(body.get('email'), str) or not isinstance(body.get('password'), str):
        return jsonify(error='Email and password are required.'), 400

    result = supabase_request('/auth/v1/token?grant_type=password', payload={
        'email': body['email'], 'password': body['password'],
    })
    return jsonify(access_token=result['access_token'])
