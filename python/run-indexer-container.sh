docker run \
    -e AR_HOST=https://annorepo.suriano.huygens.knaw.nl \
    -e AR_CONTAINER=suriano-1.0.1e-029 \
    -e ES_HOST=http://host.docker.internal:9200 \
    -e ES_INDEX=surind-029 \
    peen-indexer
