from typing import List, Union

from functools import wraps
from flask_login import current_user
from flask import render_template, url_for


def check_user_roles(
    required_roles: List = [],
    excluded_roles: List = [],
):
    def decorator(function):
        @wraps(function)
        def wrapped_function(*args, **kwargs):
            if current_user is None:
                return render_template("errors/403.html"), 403

            user_roles = set(current_user.get_roles_as_list())
            if (
                not required_roles or user_roles.intersection(required_roles)
            ) and not user_roles.intersection(excluded_roles):
                return function(*args, **kwargs)
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