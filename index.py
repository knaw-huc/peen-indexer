import os
import sys
from pathlib import Path

import requests
import yaml
from annorepo.client import AnnoRepoClient, ContainerAdapter
from elasticsearch import ApiError, Elasticsearch
from loguru import logger

from SearchResultAdapter import SearchResultAdapter

MAPPING_FILE = "mapping.json"

type Query = dict[str, str]


def reset_index(
    elastic: Elasticsearch, index_name: str, path: str | os.PathLike
) -> None:
    if elastic.indices.exists(index=index_name):
        logger.trace("Deleting ES index {index_name}", index_name=index_name)
        try:
            res = elastic.indices.delete(index=index_name)
            logger.success("Deleted ES index {}: {}", index_name, res)
        except ApiError as err:
            logger.critical(err)
            sys.exit(-1)

    mapping_path = Path(path)
    logger.trace(
        "Creating ES index {} using mapping file: {}", index_name, mapping_path
    )
    try:
        res = elastic.indices.create(
            index=index_name, body=mapping_path.read_text(encoding="utf-8")
        )
        logger.success("Created ES index {}: {}", index_name, res)
    except ApiError as err:
        logger.critical(err)
        sys.exit(-2)


def store_document(elastic: Elasticsearch, index: str, doc: dict[str, any]) -> None:
    doc_id = doc["id"]
    resp = elastic.index(index=index, id=doc_id, document=doc)
    logger.trace(resp)
    if resp["result"] == "created":
        logger.success("Indexed {}", doc_id)
    else:
        logger.critical("Indexing {} failed: {}", doc_id, resp)
        sys.exit(-3)


def index_views(container: ContainerAdapter, elastic: Elasticsearch, index: str, query: Query,
                fields: dict[str, str], views: dict[str, str]) -> None:
    logger.trace("views: {}", views)
    top_tier_anno_search: SearchResultAdapter = SearchResultAdapter(container, query)
    for anno in top_tier_anno_search.items():
        logger.trace("anno: {}", anno)

        target = anno.first_target_with_selector("Text")
        selector = target["selector"]
        overlap_query = {
            ":overlapsWithTextAnchorRange": {
                "source": target["source"],
                "start": selector["start"],
                "end": selector["end"],
            },
        }

        letter_id = anno.path("body.id")
        for view in views:
            for constraint in view['constraints']:
                overlap_query[constraint['path']] = constraint['value']
            logger.trace(" - overlap query: {}", overlap_query)
            overlap_search: SearchResultAdapter = SearchResultAdapter(container, overlap_query)
            overlap_anno = next(overlap_search.items())
            logger.trace(" - overlap_anno: {}", overlap_anno)

            text_target = overlap_anno.first_target_without_selector("LogicalText")
            resp = requests.get(text_target["source"], timeout=5)
            if resp.status_code != 200:
                logger.warning("Failed to get text for {}: {}", overlap_anno.path("body.id"), resp)
            else:
                view_text = "".join(resp.json())
                logger.trace(" - text=[{}]", view_text)

                doc = {
                    "id": f"{letter_id}_{view['name']}",
                    "letterId": letter_id,
                    "viewType": view['name'],
                    "text": "".join(view_text)
                }

                for es_field, path in fields.items():
                    doc[es_field] = anno.path(path)

                logger.trace(" - es_doc: {}", doc)
                store_document(elastic, index, doc)


def main(
    ar_host: str, ar_container: str, es_host: str, es_index: str, conf: dict[str, any]
) -> None:
    print(f"Indexing {ar_host}/{ar_container} to {es_host}/{es_index}")
    annorepo = AnnoRepoClient(ar_host)
    container = annorepo.container_adapter(ar_container)
    logger.info("AnnoRepo: {about}", about=annorepo.get_about())

    elastic = Elasticsearch(es_host)
    logger.info("ElasticSearch: {info}", info=elastic.info())

    reset_index(elastic, es_index, MAPPING_FILE)

    index_views(
        container,
        elastic,
        es_index,
        query={"body.type": conf["topTier"]},
        fields=conf["fields"],
        views=conf["views"]
    )


if __name__ == "__main__":
    import argparse

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
        default="config.yml",
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
        config = yaml.safe_load(file)
        main(
            args.annorepo_host,
            args.annorepo_container,
            args.elastic_host,
            args.elastic_index,
            config,
        )
