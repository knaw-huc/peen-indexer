#! /bin/sh

set -e

exec python ./index.py \
        --annorepo-host $AR_HOST \
        --annorepo-container $AR_CONTAINER \
        --elastic-host $ES_HOST \
        --elastic-index $ES_INDEX
