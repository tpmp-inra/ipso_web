import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
import re

from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_babel import Babel, lazy_gettext as _l
from flask_moment import Moment
from flask_uploads import configure_uploads, UploadSet, DATA
from flask_caching import Cache

from celery import Celery

reg = re.compile("export (?P<name>\w+)(\=(?P<value>.+))*")
for line in open("./init_config.sh"):
    m = reg.match(line)
    if m:
        name = m.group("name")
        value = ""
        if m.group("value"):
            value = m.group("value")
        os.putenv(name, value)

from config import Config


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = "auth.login"
login.login_message = _l("Please log in to access this page.")
mail = Mail()
bootstrap = Bootstrap()
moment = Moment()
babel = Babel()
jsons = UploadSet("jsons", DATA)
cache = Cache()
celery = Celery(__name__, broker=Config.CELERY_BROKER_URL)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app)
    cache.init_app(app)
    configure_uploads(app, jsons)
    celery.conf.update(app.config)

    from app.auth import bp as auth_bp
    from app.errors import bp as errors_bp
    from app.main import bp as main_bp
    from app.database import bp as database_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(errors_bp, url_prefix="/errors")
    app.register_blueprint(main_bp)
    app.register_blueprint(database_bp, url_prefix="/database")

    if not os.path.exists("logs"):
        os.mkdir("logs")
    logging.basicConfig(
        filename=os.path.join("logs", "log.log"),
        filemode="a",
        level=logging.INFO,
        format="[%(asctime)s - %(name)s - %(levelname)s] - %(message)s",
    )
    logger = logging.getLogger("IPSO WEB")
    logger.info(
        "_________________________________________________________________________"
    )
    logger.info("Launching IPSO WEB")

    return app


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(current_app.config["LANGUAGES"])


from app import models