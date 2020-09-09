import os
from datetime import datetime
import json
import logging
from flask import render_template, flash, redirect, url_for, request, g, jsonify, session
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from werkzeug.utils import secure_filename
from app import db
from app.models import User
from app.translate import translate
from app.main import bp
from app.main.forms import LoadScriptOrStateForm, EmptyForm, EditProfileForm

logger = logging.getLogger(__name__)


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())


@bp.route("/", methods=["GET", "POST"])
@bp.route("/index", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@bp.route("/launch", methods=["GET", "POST"])
@login_required
def launch():
    upload_form = LoadScriptOrStateForm()
    if upload_form.validate_on_submit():
        try:
            j = json.load(upload_form.script_or_stored_state.data)
            if "script" in j:
                session["stored_state"] = j
            elif "title" in j:
                session["pipeline"] = j
            else:
                flash(_("Unknown file"))
            print(j)
        except Exception as e:
            flash(_("Unable to load file, only IPSO Phen files are allowed"))
            logger.exception(repr(e))

    return render_template(
        "launch.html",
        title=_("Launch"),
        upload_form=upload_form,
    )


@bp.route("/user/<username>")
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    form = EmptyForm()
    return render_template(
        "user.html",
        user=user,
        form=form,
    )


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_("Your changes have been saved."))
        return redirect(url_for("main.edit_profile"))
    elif request.method == "GET":
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template("edit_profile.html", title=_("Edit Profile"), form=form)
