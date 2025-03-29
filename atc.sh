#!/bin/sh
. .venv/bin/activate
celery -A fgserver worker -Q atc
