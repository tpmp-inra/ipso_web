from typing import List, Union

from functools import wraps
from flask_login import current_user
from flask import render_template, url_for


def role_required(required_role: Union[str, List] = ""):
    def decorator(function):
        @wraps(function)
        def wrapped_function(*args, **kwargs):
            if current_user is None:
                return render_template("errors/403.html"), 403
            if not required_role:
                return function(*args, **kwargs)
            user_roles = current_user.get_roles_as_list()
            if isinstance(required_role, str) and (required_role in user_roles):
                return function(*args, **kwargs)
            elif isinstance(required_role, list):
                for rq_subset in required_role:
                    if rq_subset in user_roles:
                        return required_role in user_roles
                return render_template("errors/403.html"), 403
            else:
                return render_template("errors/403.html"), 403

        return wrapped_function

    return decorator


def group_required(required_group: Union[str, List] = ""):
    def decorator(function):
        @wraps(function)
        def wrapped_function(*args, **kwargs):
            if current_user is None:
                return render_template("errors/403.html"), 403
            if not required_group:
                return function(*args, **kwargs)
            user_group = current_user.get_groups_as_list()
            if isinstance(required_group, str) and (required_group in user_group):
                return function(*args, **kwargs)
            elif isinstance(required_group, list):
                for rq_subset in required_group:
                    if rq_subset in user_group:
                        return required_group in user_group
                return render_template("errors/403.html"), 403
            else:
                return render_template("errors/403.html"), 403

        return wrapped_function

    return decorator