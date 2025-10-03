run:
	peen-indexer \
		--annorepo-host=https://preview.dev.diginfra.org/annorepo \
		--annorepo-container=israels \
		--config ./indexer/config.yml \
		--elastic-host=http://localhost:9200 \
		--elastic-index=isrent
#	--trace
