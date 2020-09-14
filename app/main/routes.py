import os
from datetime import datetime
import logging
import pathlib

from alembic import script
from flask import render_template, flash, redirect, url_for, request, g, session, jsonify
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from celery.task.control import revoke

from app import db, jsons
from app.models import User
from app.main import bp
from app.main.forms import (
    EmptyForm,
    EditProfileForm,
    CommonOptions,
    ScriptOptions,
    UploadForm,
    LaunchProcess,
    ReviewForm,
)
from app.funs import (
    get_source_configuration,
    get_launch_configuration,
    set_launch_configuration,
    long_task,
    get_process_info,
    get_abort_file_path,
)

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


@bp.route("/review", methods=["GET", "POST"])
@login_required
def review():
    review_form = ReviewForm()
    if review_form.validate_on_submit() and review_form.go_back.data:
        return redirect(url_for("main.prepare"))
    if review_form.validate_on_submit() and review_form.execute.data:
        return redirect(url_for("main.execute"))

    data = get_launch_configuration(current_user.username)
    if not data:
        flash("No launch configuration data available", category="error")
    return render_template(
        template_name_or_list="review.html",
        review_form=review_form,
        launch_info=get_process_info(data),
    )


@bp.route("/execute", methods=["GET", "POST"])
@login_required
def execute():
    data = get_launch_configuration(current_user.username)
    if not data:
        flash("No launch configuration data available", category="error")
    return render_template(
        template_name_or_list="execute.html",
        launch_info=get_process_info(data),
        back_link="/revoke_queue",
    )


@bp.route("/prepare", methods=["GET", "POST"])
@login_required
def prepare():
    upload_form = UploadForm()
    if upload_form.validate_on_submit() and upload_form.upload_data.data:
        try:
            data = upload_form.input_file.data
            target_file = f"{current_user.username}_{data.filename}"
            session["loaded_file_name"] = data.filename
            try:
                if os.path.isfile(jsons.path(target_file)):
                    os.remove(jsons.path(target_file))
            except Exception as e:
                flash(repr(e), category="error")
                logger.exception(repr(e))
            session["script_or_stored_state"] = jsons.save(
                storage=data,
                name=target_file,
            )
        except Exception as e:
            flash(
                _("Unable to load file, only IPSO Phen files are allowed"),
                category="error",
            )
            del session["script_or_stored_state"]
            del session["loaded_file_name"]
            logger.exception(repr(e))

    if "script_or_stored_state" in session:
        data = get_source_configuration(jsons.path(session["script_or_stored_state"]))
        common_form = CommonOptions(
            thread_count=data["thread_count"],
            csv_file_name=data["csv_file_name"],
            overwrite_existing=data["overwrite_existing"],
            build_annotation_csv=data["build_annotation_csv"],
        )
        if data.get("standalone", False) is True:
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
    if launch_form.validate_on_submit() and launch_form.review.data:
        data = get_source_configuration(
            jsons.path(session.get("script_or_stored_state", ""))
        )
        if data is None or "script_or_stored_state" not in session:
            flash(
                _("Please load a pipeline or a stored state before proceeding"),
                category="error",
            )
        elif data.get("standalone", False) is False and not script_form.image_list.data:
            flash(_("Please add images before proceeding"), category="error")
        elif data.get("standalone", False) is True and not data["images"]:
            flash(_("Please add images before proceeding"), category="error")
        else:
            set_launch_configuration(
                user_name=current_user.username,
                data=data,
                csv_file_name=common_form.csv_file_name.data,
                overwrite_existing=common_form.overwrite_existing.data,
                generate_series_id=common_form.generate_series_id.data,
                series_id_time_delta=common_form.series_id_time_delta.data,
                thread_count=common_form.thread_count.data,
                build_annotation_csv=common_form.build_annotation_csv.data,
                images=script_form.image_list.data
                if data.get("standalone", False) is False
                else data["images"],
                current_user=current_user.username,
            )
            return redirect(url_for("main.execute"))

    return render_template(
        "prepare.html",
        title=_("Launch"),
        upload_form=upload_form,
        common_form=common_form,
        script_form=script_form,
        images=images,
        launch_form=launch_form,
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


@bp.route("/revoke_queue", methods=["POST"])
@login_required
def revoke_queue():
    pathlib.Path(get_abort_file_path(current_user.username)).touch()
    return redirect(url_for("main.prepare"))


@bp.route("/init_queue", methods=["POST"])
@login_required
def init_queue():
    abort_path = get_abort_file_path(current_user.username)
    if os.path.isfile(abort_path):
        os.remove(abort_path)
    task = long_task.delay(
        **get_launch_configuration(current_user.username),
    )
    session["task_id"] = task.id
    return (
        jsonify({}),
        202,
        {"Location": url_for("main.taskstatus", task_id=task.id)},
    )


@bp.route("/taskstatus/<task_id>")
@login_required
def taskstatus(task_id):
    task = long_task.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"state": task.state, "current": 0, "total": 1, "status": "Pending..."}
    elif task.state != "FAILURE":
        response = {
            "state": task.state,
            "current": task.info.get("current", 0),
            "total": task.info.get("total", 1),
            "status": task.info.get("status", ""),
        }
        if "result" in task.info:
            response["result"] = task.info["result"]
    else:
        # something went wrong in the background job
        response = {
            "state": task.state,
            "current": 1,
            "total": 1,
            "status": str(task.info),  # this is the exception raised
        }
    return jsonify(response)
