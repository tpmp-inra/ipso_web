from datetime import datetime
from hashlib import md5
from time import time
from enum import Enum


from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from app import db, login, Config

# Available roles
ROLE_SUPER_ADMIN = "super_admin"
ROLE_GROUP_ADMIN = "group_admin"
ROLE_USER = "user"
AVAILABLE_ROLES = [ROLE_GROUP_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER]

# Available groups
GROUP_TPMP = "TPMP"
GROUP_OTHERS = "others"
AVAILABLE_GROUPS = [GROUP_TPMP, GROUP_OTHERS]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    roles = db.Column(db.String(120))
    groups = db.Column(db.String(120))

    def __repr__(self):
        return "<User {}>".format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {"reset_password": self.id, "exp": time() + expires_in},
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        ).decode("utf-8")

    def get_roles_as_list(self):
        return self.roles.split(",") if self.roles else []

    def get_groups_as_list(self):
        return self.groups.split(",") if self.groups else []

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )["reset_password"]
        except:
            return
        return User.query.get(id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Database(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    jump_address = db.Column(db.String(64), index=True, unique=True)
    host_address = db.Column(db.String(64), index=True, unique=True)

    def config_exists(self):
        return any([self.name in key for key in current_app.config.keys])

    def jump_user(self):
        if self.config_exists():
            return current_app.config[self.name + "_JUMP_USER"]

    def host_user(self):
        if self.config_exists():
            return current_app.config[self.name + "_HOST_USER"]

    def jump_pwd(self):
        if self.config_exists():
            return current_app.config[self.name + "_JUMP_PWD"]

    def host_pwd(self):
        if self.config_exists():
            return current_app.config[self.name + "_HOST_PWD"]
