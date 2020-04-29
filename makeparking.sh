#!/bin/sh
. /opt/virtual_fgatc/bin/activate
export DJANGO_SETTINGS_MODULE=fgserver.settings
FGATC_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd $FGATC_DIR
python ${FGATC_DIR}/fgserver/tools/make_parkings.py $*
