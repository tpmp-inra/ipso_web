from flask_login import current_user, login_required
from flask import render_template, url_for

from app.database import bp
from app.auth.funs import check_user_roles


@bp.route("/select_database", methods=["GET", "POST"])
@login_required
def select_database():
    return render_template("database/select_database.html")


@bp.route("/remove_database", methods=["GET", "POST"])
@login_required
@check_user_roles(required_roles=["admin"])
def remove_database():
    return render_template(template_name_or_list="database/remove_database.html")


@bp.route("/add_database", methods=["GET", "POST"])
@login_required
@check_user_roles(required_roles=["admin"])
def add_database():
    return render_template(template_name_or_list="database/add_database.html")
