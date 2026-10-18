# app/routes/users.py
from urllib.parse import quote
from uuid import UUID

from flask import Blueprint, jsonify, request
from app.services.authorization import current_user, has_role, require_roles
from app.services.event_store import (
    StoreError,
    supabase_admin_request,
    supabase_request,
    authenticated_token,
)

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


@users.get('/users/me')
def get_current_user():
    token = authenticated_token(supabase_request)
    auth_user = supabase_request('/auth/v1/user', token=token)
    user_id = auth_user.get('id')

    identity = current_user()
    profile_rows = supabase_admin_request(
        f'/rest/v1/users?select=name,email&user_id=eq.{quote(user_id, safe="")}'
    )
    profile = profile_rows[0] if profile_rows else {}
    name = (profile.get('name') or '').strip()
    if not name:
        name = (profile.get('email') or auth_user.get('email') or '').strip()
    if '@' in name:
        name = name.split('@', 1)[0]

    role_names = list(dict.fromkeys(
        " ".join(role.title() for role in role_name.split())
        for role_name in sorted(identity.roles)
    ))

    return jsonify(user={'name': name, 'roles': role_names})


@users.get('/users')
def get_users_by_ids():
    identity = current_user()

    ids_param = request.args.get('ids', '').strip()
    role_filter = request.args.get('role', '').strip().casefold()
    if ids_param and role_filter:
        return jsonify(error='Choose either a user ID filter or a role filter.'), 400

    if role_filter == 'event_coordinator':
        require_roles("Event Coordinator Lead")
        role_rows = supabase_admin_request('/rest/v1/roles?select=role_id,role_name')
        role_ids = [
            str(row['role_id'])
            for row in role_rows
            if str(row.get('role_name', '')).strip().replace('_', ' ').casefold()
            == 'event coordinator'
            and row.get('role_id') is not None
        ]
        if role_ids:
            memberships = supabase_admin_request(
                '/rest/v1/user_roles?select=user_id&role_id=in.('
                + ','.join(quote(role_id, safe="") for role_id in role_ids) + ')'
            )
            user_ids = list(dict.fromkeys(
                str(row['user_id'])
                for row in memberships
                if row.get('user_id')
            ))
            rows = supabase_admin_request(
                '/rest/v1/users?select=user_id,name,email&user_id=in.('
                + ','.join(quote(user_id, safe="") for user_id in user_ids) + ')&order=name.asc'
            ) if user_ids else []
        else:
            rows = []
    elif role_filter:
        return jsonify(error='Unsupported user role filter.'), 400
    elif ids_param:
        require_roles("Event Coordinator", "Event Organiser")
        id_list = []
        for raw_id in ids_param.split(','):
            try:
                id_list.append(str(UUID(raw_id.strip())))
            except ValueError:
                continue
        if not id_list:
            return jsonify(users={})
        event_rows = supabase_admin_request(
            "/rest/v1/events?select=event_organiser_id,event_coordinator_id"
            f"&or=(event_organiser_id.eq.{quote(identity.user_id, safe='')},"
            f"event_coordinator_id.eq.{quote(identity.user_id, safe='')})"
        )
        associated_ids = {
            str(event.get(field))
            for event in event_rows
            for field in (
                "event_organiser_id",
                "event_coordinator_id",
                "technical_support_id",
                "venue_staff_id",
            )
            if event.get(field)
        }
        allowed_ids = [user_id for user_id in id_list if user_id in associated_ids]
        rows = supabase_admin_request(
            '/rest/v1/users?select=user_id,name,email&user_id=in.('
            + ','.join(quote(user_id, safe="") for user_id in allowed_ids) + ')'
        ) if allowed_ids else []
    else:
        return jsonify(error='Choose a role or user ID filter.'), 400

    users_map = {}
    for row in rows:
        user_id = row.get('user_id')
        name = (row.get('name') or row.get('email') or '').strip()
        if not name and row.get('email'):
            name = row['email'].split('@', 1)[0].strip()
        if user_id and name:
            users_map[str(user_id)] = name

    return jsonify(users=users_map)