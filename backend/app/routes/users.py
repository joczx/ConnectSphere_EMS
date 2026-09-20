# app/routes/users.py
from flask import Blueprint, jsonify, request
from app.services.event_store import StoreError, supabase_request, authenticated_token

users = Blueprint('users', __name__, url_prefix='/api')


@users.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

@users.errorhandler(StoreError)
def handle_store_error(error):
    return jsonify(error.to_dict()), error.status


# def authenticated_token():
#     scheme, _, token = request.headers.get('Authorization', '').partition(' ')
#     if scheme.lower() != 'bearer' or not token.strip():
#         raise StoreError(401)
#     user = supabase_request('/auth/v1/user', token=token)
#     if not user.get('id'):
#         raise StoreError(401)
#     return token


@users.get('/users')
def get_users_by_ids():
    token = authenticated_token()

    ids_param = request.args.get('ids', '')
    id_list = [uid.strip() for uid in ids_param.split(',') if uid.strip()]
    if not id_list:
        return jsonify(users={})

    ids_filter = ','.join(id_list)
    rows = supabase_request(
        f'/rest/v1/users?select=user_id,name,email&user_id=in.({ids_filter})',
        token=token,
    )

    users_map = {}
    for row in rows:
        user_id = row.get('user_id')
        name = (row.get('name') or row.get('email') or '').strip()
        if not name and row.get('email'):
            name = row['email'].split('@', 1)[0].strip()
        if user_id and name:
            users_map[str(user_id)] = name

    return jsonify(users=users_map)