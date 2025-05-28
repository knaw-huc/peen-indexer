import argparse
import sys

from indexer.index import CONFIG_DEFAULT, logger, main

parser = argparse.ArgumentParser(
    description="index annorepo container to elastic index"
)
parser.add_argument(
    "--annorepo-host", metavar="path", required=True, help="the AnnoRepo host"
)
parser.add_argument(
    "--annorepo-container",
    metavar="path",
    required=True,
    help="the AnnoRepo container on annorepo-host",
)
parser.add_argument(
    "--elastic-host",
    metavar="path",
    required=False,
    default="http://localhost:9200",
    help="the ElasticSearch host name",
)
parser.add_argument(
    "--elastic-index",
    metavar="path",
    required=True,
    help="the ElasticSearch index name",
)
parser.add_argument(
    "--config",
    metavar="path",
    required=False,
    default=CONFIG_DEFAULT,
    help="configuration file",
)
parser.add_argument(
    "--trace",
    required=False,
    action="store_true",
    help="run indexer with logging in trace mode",
)
args = parser.parse_args()

if args.trace:
    logger.remove()
    logger.add(sys.stderr, level="TRACE")

with open(args.config, "r", encoding="utf-8") as file:
    main(
        args.annorepo_host,
        args.annorepo_container,
        args.elastic_host,
        args.elastic_index,
        args.config,
        True
    )
