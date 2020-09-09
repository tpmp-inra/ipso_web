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


class CommonOptions(FlaskForm):
    thread_count = IntegerField(
        label=f"Thread count from 1 to {mp.cpu_count() - 1}",
        validators=[NumberRange(min=0, max=mp.cpu_count() - 1)],
        default=1,
    )
    csv_out_name = StringField(label=_("Output file name"))
    overwrite = BooleanField(label=_("Overwrite"))
    build_annotation_csv = BooleanField(label=_("Build annotation CSV"))
    generate_series_id = BooleanField(label=_("Generate series IDs"))
    series_id_delta = IntegerField(label="Max delta for series Id", default=20)


class ScriptOptions(FlaskForm):
    image_list = MultipleFileField(label="Images to analyse")


class EmptyForm(FlaskForm):
    submit = SubmitField("Submit")


class LaunchProcess(FlaskForm):
    launch = SubmitField("Launch")


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
