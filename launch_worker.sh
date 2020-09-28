#!/bin/zsh

source ./init_config.sh

env/bin/celery worker -A celery_worker.celery --loglevel=info