from email.policy import default
import multiprocessing as mp

from flask import request
from flask_wtf import FlaskForm
from jinja2.nodes import Mul
from wtforms import (
    StringField,
    SubmitField,
    TextAreaField,
    IntegerField,
    BooleanField,
    MultipleFileField,
    SelectField,
)
from wtforms.validators import (
    ValidationError,
    DataRequired,
    Length,
    NumberRange,
)
from flask_babel import _, lazy_gettext as _l
from wtforms import FileField

from app.models import User


class UploadForm(FlaskForm):
    input_file = FileField("")
    upload_data = SubmitField("Upload data")
    database = SelectField(
        label="Database",
        choices=[("phenoserre", "Phenoserre"), ("phenopsis", "Phenopsis")],
        validate_choice=False,
    )


class StateProcessOptions(FlaskForm):
    experiment = SelectField(
        label="Experiment",
        validate_choice=False,
    )
    thread_count = IntegerField(
        label=f"Thread count from 1 to {mp.cpu_count() - 1}",
        validators=[NumberRange(min=0, max=mp.cpu_count() - 1)],
        default=1,
    )
    overwrite_existing = BooleanField(label=_("Overwrite"))
    build_annotation_csv = BooleanField(label=_("Build annotation CSV"))
    generate_series_id = BooleanField(label=_("Generate series IDs"))
    series_id_time_delta = IntegerField(label="Max delta for series Id", default=20)

    back = SubmitField("< Back")
    review = SubmitField("Review & execute >")


class ReviewForm(FlaskForm):
    go_back = SubmitField("< Back")
    execute = SubmitField("Execute >")


class EmptyForm(FlaskForm):
    submit = SubmitField("submit")


class EditProfileForm(FlaskForm):
    username = StringField(_l("Username"), validators=[DataRequired()])
    about_me = TextAreaField(_l("About me"), validators=[Length(min=0, max=140)])
    submit = SubmitField(_l("Submit"))

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError(_("Please use a different username."))
