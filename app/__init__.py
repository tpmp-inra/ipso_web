import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os

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

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.errors import bp as errors_bp

    app.register_blueprint(errors_bp)

    from app.main import bp as main_bp

    app.register_blueprint(main_bp)

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