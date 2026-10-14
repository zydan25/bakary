"""Server-enforced route permissions."""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def permission_required(permission_code):
    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.has_permission(permission_code):
                abort(403)
            return view_function(*args, **kwargs)

        return wrapped

    return decorator
