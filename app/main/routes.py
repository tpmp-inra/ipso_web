import os
from datetime import datetime
import time
import logging
import pathlib
from datetime import datetime as dt
import multiprocessing as mp
import json

import plotly

from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    g,
    session,
    jsonify,
    Response,
)
from flask_login import current_user, login_required
from flask_babel import _, get_locale

from app import db, jsons
from app.models import User
from app.main import bp
from app.main.forms import (
    EmptyForm,
    EditProfileForm,
    StateProcessOptions,
    UploadForm,
)
from app.funs import (
    get_source_configuration,
    get_launch_configuration,
    set_launch_configuration,
    long_task,
    get_process_info,
    get_abort_file_path,
    prepare_process_muncher,
    generate_annotation_csv,
)
from app.auth.funs import check_user_roles

from ipapi.database.db_initializer import available_db_dicts, DbType

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
    return render_template(
        template_name_or_list="index.html",
        message="",
    )


@bp.route("/select_pipeline_and_database", methods=["GET", "POST"])
@check_user_roles(excluded_roles=["pending"])
@login_required
def select_pipeline_and_database():
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
            session["pipeline"] = jsons.save(
                storage=data,
                name=target_file,
            )
            session["database"] = upload_form.database.data
        except Exception as e:
            flash(
                _("Unable to load file, only IPSO Phen files are allowed"),
                category="error",
            )
            session.pop("pipeline", None)
            session.pop("loaded_file_name", None)
            logger.exception(repr(e))
        else:
            return redirect(url_for("main.prepare"))

    return render_template(
        "select_pipeline_and_database.html",
        title=_("Upload"),
        upload_form=upload_form,
    )


@bp.route("/prepare", methods=["GET", "POST"])
@login_required
def prepare():
    data = get_source_configuration(jsons.path(session.get("pipeline", "")))
    if data is None:
        flash(
            _("Please load a pipeline or a stored state before proceeding"),
            category="error",
        )
        return redirect(url_for("main.select_pipeline_and_database"))

    process_options_form = StateProcessOptions(
        thread_count=data["thread_count"],
        overwrite_existing=data["overwrite_existing"],
        build_annotation_csv=data["build_annotation_csv"],
    )
    db_selected = session.get("database", "")
    if db_selected == "phenoserre":
        db_selector = DbType.PHENOSERRE
    elif db_selected == "phenopsis":
        db_selector = DbType.PHENOPSIS
    else:
        db_selector = DbType.CUSTOM_DB
    process_options_form.experiment.choices = [
        (dbi.to_json(), dbi.display_name) for dbi in available_db_dicts[db_selector]
    ]

    process_options_form.thread_count.choices = [
        (str(i), str(i)) for i in range(1, mp.cpu_count())
    ]

    if process_options_form.validate_on_submit() and process_options_form.review.data:
        set_launch_configuration(
            user_name=current_user.username,
            data=data,
            csv_file_name=data["csv_file_name"],
            overwrite_existing=process_options_form.overwrite_existing.data,
            sub_folder_name=data["sub_folder_name"]
            if data["sub_folder_name"]
            else f"{current_user.username}_{dt.now().strftime('%Y%b%d%H%M%S')}",
            generate_series_id=process_options_form.generate_series_id.data,
            series_id_time_delta=process_options_form.series_id_time_delta.data,
            thread_count=process_options_form.thread_count.data,
            build_annotation_csv=process_options_form.build_annotation_csv.data,
            current_user=current_user.username,
            database_info=process_options_form.experiment.data,
        )
        return redirect(url_for("main.review"))
    elif process_options_form.validate_on_submit() and process_options_form.back.data:
        return redirect(url_for("main.select_pipeline_and_database"))
    else:
        return render_template(
            "prepare.html",
            title=_("Launch"),
            process_options_form=process_options_form,
        )


@bp.route("/review", methods=["GET", "POST"])
@login_required
def review():
    data = get_launch_configuration(current_user.username)
    if not data:
        flash("No launch configuration data available", category="error")

    launch_info = get_process_info(data)
    plot = json.dumps(
        launch_info.pop("fig"),
        cls=plotly.utils.PlotlyJSONEncoder,
    )

    return render_template(
        template_name_or_list="review.html",
        launch_info=launch_info,
        back_link="/prepare",
        back_text="< Back",
        back_type="primary",
        forward_text="Execute >",
        forward_link="/execute",
        forward_type="primary",
        forward_state="enabled" if data else "disabled",
        use_redis=False,
        plot=plot,
    )


@bp.route("/execute", methods=["GET", "POST"])
@login_required
def execute():
    return render_template(
        template_name_or_list="execute.html",
        back_link="/revoke_queue",
        use_redis=False,
    )


@bp.route("/execute_task")
@login_required
def execute_task():
    abort_path = get_abort_file_path(current_user.username)
    if os.path.isfile(abort_path):
        os.remove(abort_path)

    launch_conf = get_launch_configuration(current_user.username)

    def abort_callback():
        return os.path.isfile(abort_path)

    def wrapper():
        yield f'data: {{"header": "Building pipeline processor..."}}\n\n'

        data = prepare_process_muncher(None, abort_callback, **launch_conf)

        pp = data["pipeline_processor"]
        output_folder = data["output_folder"]

        time.sleep(0.1)
        yield f'data: {{"header": "Preparing images..."}}\n\n'
        for data in pp.yield_groups(launch_conf["series_id_time_delta"]):
            yield f'data: {{"current":"{data["step"] + 1}","total":"{data["total"]}"}}\n\n'
        groups_to_process = pp.groups_to_process

        # Generate annotation CSV
        if launch_conf["build_annotation_csv"]:
            time.sleep(0.1)
            yield f'data: {{"header": "Generating DI CSV..."}}\n\n'
            generate_annotation_csv(
                pipeline_processor=pp,
                groups_to_process=groups_to_process,
                output_folder=output_folder,
                di_filename=os.path.join(
                    output_folder,
                    f"{launch_conf['csv_file_name']}_diseaseindex.csv",
                ),
            )

        time.sleep(0.1)
        yield f'data: {{"header": "Analyzing images...","current":"0","total":"1"}}\n\n'
        for data in pp.yield_test_process_groups(groups_list=groups_to_process):
            yield f'data: {{"current":"{data["step"] + 1}","total":"{data["total"]}"}}\n\n'

        if os.path.isfile(abort_path):
            time.sleep(0.1)
            yield f'data: {{"header": "User abort", "close": "true"}}\n\n'
        else:
            time.sleep(0.1)
            yield f'data: {{"header": "Merging data...","current":"0","total":"1"}}\n\n'
            for data in pp.yield_merge_result_files(
                csv_file_name=launch_conf["csv_file_name"] + ".csv"
            ):
                yield f'data: {{"current":"{data["step"] + 1}","total":"{data["total"]}"}}\n\n'
            time.sleep(0.1)
            yield f'data: {{"header": "42", "close": "true"}}\n\n'

    return Response(wrapper(), mimetype="text/event-stream")


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
    return redirect(url_for("main.review"))


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
