import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    # Secret key WIP
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or "thisisasecretkeythekeyisasecretandisnotshapedlikeakey"
    )
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "ipso_web.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Uploads path
    UPLOADED_JSONS_DEST = "uploads/jsons"
    # Mail WIP
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 25)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS") is not None
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    # Admin WIP
    ADMINS = ["your-email@example.com"]
    # Languages WIP
    LANGUAGES = ["en", "es"]
    MS_TRANSLATOR_KEY = os.environ.get("MS_TRANSLATOR_KEY")
    # Cache configuration
    CACHE_TYPE = "simple"
    # Celery configuration
    CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
