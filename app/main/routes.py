from datetime import datetime
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    g,
    jsonify,
    current_app,
)
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from app import db
from app.models import User
from app.translate import translate
from app.main import bp
from app.main.forms import LaunchForm


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())


@bp.route("/", methods=["GET", "POST"])
@bp.route("/index", methods=["GET", "POST"])
@login_required
def index():
    form = LaunchForm()

    return render_template(
        "index.html",
        title=_("Launch"),
        form=form,
    )
