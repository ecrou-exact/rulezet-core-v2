import re
from ..core.db_class.user import User

_EMAIL_RE   = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_HANDLE_RE  = re.compile(r'^[a-zA-Z0-9_\-\.]{1,50}$')
_PHONE_RE   = re.compile(r'^[\+\d\s\-\(\)\.]{7,25}$')
_URL_PREFIX = re.compile(r'^https?://', re.I)


def _safe(v, max_len=255):
    if not v:
        return None
    v = str(v).strip()
    return v[:max_len] if v else None


def verif_add_user(data: dict) -> dict:
    fn = _safe(data.get('first_name'), 64)
    if not fn:
        return {'message': 'first_name is required'}

    ln = _safe(data.get('last_name'), 64)
    if not ln:
        return {'message': 'last_name is required'}

    email = _safe(data.get('email'), 128)
    if not email:
        return {'message': 'email is required'}
    if not _EMAIL_RE.match(email):
        return {'message': 'Invalid email format'}
    if User.query.filter_by(email=email).first():
        return {'message': 'Email already registered'}

    pwd = data.get('password', '')
    if not pwd or len(pwd) < 8:
        return {'message': 'Password must be at least 8 characters'}
    if not re.search(r'[A-Z]', pwd):
        return {'message': 'Password must contain an uppercase letter'}
    if not re.search(r'[a-z]', pwd):
        return {'message': 'Password must contain a lowercase letter'}
    if not re.search(r'\d', pwd):
        return {'message': 'Password must contain a digit'}

    return {
        'first_name': fn,
        'last_name':  ln,
        'email':      email,
        'password':   pwd,
        'role_id':    int(data.get('role_id', 2)),
    }


def verif_edit_user(data: dict, user_id: int) -> dict:
    user = User.query.get(user_id)
    if not user:
        return {'message': 'User not found'}

    result = {}

    fn = _safe(data.get('first_name'), 64)
    result['first_name'] = fn or user.first_name

    ln = _safe(data.get('last_name'), 64)
    result['last_name'] = ln or user.last_name

    email = _safe(data.get('email'), 128)
    if email:
        if not _EMAIL_RE.match(email):
            return {'message': 'Invalid email format'}
        if email != user.email and User.query.filter_by(email=email).first():
            return {'message': 'Email already in use'}
        result['email'] = email
    else:
        result['email'] = user.email

    # Profile fields — all optional
    for field in ('bio', 'job_title', 'company', 'location'):
        if field in data:
            result[field] = _safe(data[field], 500 if field == 'bio' else 100)

    if 'phone' in data:
        v = _safe(data['phone'], 25)
        if v and not _PHONE_RE.match(v):
            return {'message': 'Invalid phone number format'}
        result['phone'] = v

    if 'website' in data:
        v = _safe(data['website'], 200)
        if v and not _URL_PREFIX.match(v):
            v = 'https://' + v
        result['website'] = v

    if 'social_linkedin' in data:
        v = _safe(data['social_linkedin'], 200)
        if v and not _URL_PREFIX.match(v):
            v = 'https://' + v
        result['social_linkedin'] = v

    for handle_field in ('social_twitter', 'social_github', 'username_handle'):
        if handle_field in data:
            v = _safe(data[handle_field], 50)
            if v:
                v = v.lstrip('@')
                if not _HANDLE_RE.match(v):
                    return {'message': f'Invalid format for {handle_field}'}
            result[handle_field] = v

    return result
