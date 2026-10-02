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
    token = authenticated_token(supabase_request)

    ids_param = request.args.get('ids', '').strip()
    role_filter = request.args.get('role', '').strip().casefold()
    if ids_param and role_filter:
        return jsonify(error='Choose either a user ID filter or a role filter.'), 400

    if role_filter == 'event_coordinator':
        role_rows = supabase_request(
            '/rest/v1/roles?select=role_id,role_name', token=token,
        )
        role_ids = [
            str(row['role_id'])
            for row in role_rows
            if str(row.get('role_name', '')).strip().replace('_', ' ').casefold()
            == 'event coordinator'
            and row.get('role_id') is not None
        ]
        if role_ids:
            memberships = supabase_request(
                '/rest/v1/user_roles?select=user_id&role_id=in.('
                + ','.join(role_ids) + ')',
                token=token,
            )
            user_ids = list(dict.fromkeys(
                str(row['user_id'])
                for row in memberships
                if row.get('user_id')
            ))
            rows = supabase_request(
                '/rest/v1/users?select=user_id,name,email&user_id=in.('
                + ','.join(user_ids) + ')&order=name.asc',
                token=token,
            ) if user_ids else []
        else:
            rows = []
    elif role_filter:
        return jsonify(error='Unsupported user role filter.'), 400
    elif ids_param:
        id_list = [uid.strip() for uid in ids_param.split(',') if uid.strip()]
        ids_filter = ','.join(id_list)
        rows = supabase_request(
            f'/rest/v1/users?select=user_id,name,email&user_id=in.({ids_filter})',
            token=token,
        )
    else:
        rows = supabase_request(
            '/rest/v1/users?select=user_id,name,email&order=name.asc',
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