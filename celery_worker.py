#!/usr/bin/env python
import sys
import os
from app import celery, create_app

sys.path.append(os.path.join(".", "app"))

app = create_app()
app.app_context().push()