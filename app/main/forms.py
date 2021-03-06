from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    TextAreaField,
    IntegerField,
    BooleanField,
    SelectField,
)
from wtforms.validators import (
    ValidationError,
    DataRequired,
    Length,
)
from flask_babel import _, lazy_gettext as _l
from wtforms import FileField

from app.models import User


class UploadForm(FlaskForm):
    input_file = FileField("")
    upload_data = SubmitField("Configure process >")
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
    thread_count = SelectField(
        label=f"Allocated threads",
        validate_choice=False,
    )
    overwrite_existing = BooleanField(label=_("Overwrite"))
    build_annotation_csv = BooleanField(label=_("Build annotation CSV"))
    generate_series_id = BooleanField(label=_("Generate series IDs"))
    series_id_time_delta = IntegerField(label="Max delta for series Id", default=20)

    back = SubmitField("< Back")
    review = SubmitField("Review >")


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
