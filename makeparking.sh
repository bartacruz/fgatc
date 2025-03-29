#!/bin/sh
. /home/julio/src/fgatc/.venv/bin/activate
export DJANGO_SETTINGS_MODULE=fgserver.settings
python -m fgserver.tools.make_parkings $*
