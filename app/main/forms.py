from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import ValidationError, DataRequired, Length
from flask_babel import _, lazy_gettext as _l
from app.models import User


class LaunchForm(FlaskForm):
    script_or_stored_state = StringField(
        _l("Script or stored state"), validators=[DataRequired()]
    )
