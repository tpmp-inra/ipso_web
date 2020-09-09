from email.policy import default
import os
from datetime import datetime
import json
import logging
from alembic import script
from flask import render_template, flash, redirect, url_for, request, g, session
from flask_login import current_user, login_required
from flask_babel import _, get_locale

from app import db, jsons, cache
from app.models import User
from app.main import bp
from app.main.forms import (
    EmptyForm,
    EditProfileForm,
    CommonOptions,
    ScriptOptions,
    UploadForm,
    LaunchProcess,
)

logger = logging.getLogger(__name__)


@cache.memoize(timeout=180)
def get_source_configuration(url: str):
    print(f"Requested: {url}")
    with open(url, "r") as f:
        data = json.load(f)
    if "script" in data:
        if not "build_annotation_csv" in data:
            data["build_annotation_csv"] = False
        data["standalone"] = False
        return data
    elif "Pipeline" in data:
        return dict(
            csv_file_name="data.csv",
            overwrite_existing=False,
            sub_folder_name="",
            script=data,
            generate_series_id=False,
            series_id_time_delta=0,
            thread_count=1,
            build_annotation_csv=False,
            standalone=True,
            images=[],
        )
    else:
        return None


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


@bp.route("/execute", methods=["GET", "POST"])
@login_required
def execute():
    return "Now we're talking"


@bp.route("/launch", methods=["GET", "POST"])
@login_required
def launch():
    upload_form = UploadForm()
    if upload_form.validate_on_submit():
        try:
            data = upload_form.input_file.data
            target_file = f"{current_user.username}_{data.filename}"
            session["loaded_file_name"] = data.filename
            try:
                if os.path.isfile(jsons.path(target_file)):
                    os.remove(jsons.path(target_file))
            except Exception as e:
                flash(repr(e))
                logger.exception(repr(e))
            print(f"Target file: {target_file}")
            session["script_or_stored_state"] = jsons.save(
                storage=data,
                name=target_file,
            )
        except Exception as e:
            flash(_("Unable to load file, only IPSO Phen files are allowed"))
            del session["script_or_stored_state"]
            del session["loaded_file_name"]
            logger.exception(repr(e))

    if "script_or_stored_state" in session:
        data = get_source_configuration(jsons.path(session["script_or_stored_state"]))
        print(data.keys())
        common_form = CommonOptions(
            thread_count=data["thread_count"],
            csv_out_name=data["csv_file_name"],
            overwrite=data["overwrite_existing"],
            build_annotation_csv=data["build_annotation_csv"],
        )
        if data.get("standalone", False) is not True:
            images = {
                "excerpt": "\n".join(data["images"][:10]),
                "excess": len(data["images"]) - 10,
            }
            script_form = None
        else:
            script_form = ScriptOptions(image_list=data["images"])
            images = None
    else:
        common_form = None
        script_form = None
        images = None

    launch_form = LaunchProcess()
    if launch_form.validate_on_submit():
        return "Now we're talking"

    return render_template(
        "launch.html",
        title=_("Launch"),
        upload_form=upload_form,
        common_form=common_form,
        script_form=script_form,
        images=images,
        launch_form=launch_form,
        launch_btn_class="btn btn-primary"
        if "script_or_stored_state" in session
        else "btn btn-danger  disabled",
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
