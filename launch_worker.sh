#!/bin/zsh

env/bin/celery worker -A celery_worker.celery --loglevel=info