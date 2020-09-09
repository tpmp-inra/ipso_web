import sys
import os

from app import create_app, db, cli
from app.models import User

sys.path.append(os.path.join(".", "app"))

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {"db": db, "User": User}
