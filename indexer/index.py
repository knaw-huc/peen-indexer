import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
import yaml
from annorepo.client import AnnoRepoClient, ContainerAdapter
from elasticsearch import ApiError, Elasticsearch
from loguru import logger

from .SearchResultAdapter import SearchResultAdapter

MAPPING_FILE = f"{os.path.dirname(__file__)}/mapping.json"
CONFIG_DEFAULT = f"{os.path.dirname(__file__)}/config.yml"

type Query = dict[str, str]


def reset_index(
        elastic: Elasticsearch, index_name: str, path: str | os.PathLike
) -> int:
    if elastic.indices.exists(index=index_name):
        logger.trace("Deleting ES index {index_name}", index_name=index_name)
        try:
            res = elastic.indices.delete(index=index_name)
            logger.success("Deleted ES index {}: {}", index_name, res)
        except ApiError as err:
            logger.critical(err)
            return -1

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
        return -2

    return 0


def store_document(
        elastic: Elasticsearch, index: str, doc_id: str, doc: dict[str, Any]
) -> int:
    resp = elastic.index(index=index, id=doc_id, document=doc)
    logger.trace(resp)
    if resp["result"] == "created":
        logger.success("Indexed {}", doc_id)
    else:
        logger.critical("Indexing {} failed: {}", doc_id, resp)
        return -1

    return 0


def extract_name(p: dict[str, Any]) -> str:
    forename = p['forename']

    name_link = p.get('nameLink')

    surname = p['surname']
    if type(surname) is list:
        for part in surname:
            if type(part) is dict and part['tei:type'] == 'married-name':
                surname = part['text']
            else:
                surname = part

    name = surname + ", " + forename
    if name_link:
        name += " " + name_link
    return name
    # return " ".join(filter(None, [forename, name_link, surname]))


def extract_artworks(container: ContainerAdapter, overlap_query: dict[str, Any]) -> dict[str, set[str]]:
    # fetch overlapping Rs[type=artwork] annotations
    query = overlap_query.copy()
    query.update({
        "body.type": "tei:Rs",
        "body.metadata.tei:type": "artwork"
    })
    logger.trace("artworks query: {}", query)

    artworks = defaultdict(set)
    for anno in SearchResultAdapter(container, query).items():
        logger.trace("artwork_anno: {}", anno)
        for ref in anno.path("body.metadata.ref"):
            for h in ref['head']:
                lang = h['lang']
                artworks[lang].add(h['text'])

    return artworks


def extract_persons(container: ContainerAdapter, overlap_query: dict[str, Any]) -> set[str]:
    # construct query to fetch overlapping person annotations
    query = overlap_query.copy()
    query.update({
        "body.type": "tei:Rs",
        "body.metadata.tei:type": "person"
    })
    logger.trace("persons query: {}", query)

    # extract a suitable name for each person p based on "persName(full=yes)" part of annotation
    # this treats persons p1,p2 as equal based on their name, not on whether p1.id == p2.id (!)
    persons = set()
    for anno in SearchResultAdapter(container, query).items():
        anno_id = anno.path("body.id")
        logger.trace("person_anno: {}", anno)
        for ref in anno.path("body.metadata.ref"):
            if not 'persName' in ref:
                logger.error("Missing 'persName' in {}", anno_id)
                continue
            for p in ref['persName']:
                if p['full'] == 'yes':
                    if 'forename' in p and 'surname' in p:
                        persons.add(extract_name(p))
                    else:
                        logger.error("Missing 'forename' or 'surname' in {}", anno_id)

    return persons


def index_views(
        container: ContainerAdapter,
        elastic: Elasticsearch,
        index: str,
        query: Query,
        fields: dict[str, str],
        views: dict[str, str],
) -> int:
    logger.trace("views: {}", views)
    top_tier_anno_search: SearchResultAdapter = SearchResultAdapter(container, query)

    for anno in top_tier_anno_search.items():
        logger.trace("anno: {}", anno)

        doc_id = anno.path("body.id")

        target = anno.first_target_with_selector("Text")
        selector = target["selector"]
        overlap_query = {
            ":overlapsWithTextAnchorRange": {
                "source": target["source"],
                "start": selector["start"],
                "end": selector["end"],
            },
        }

        doc = {}

        for es_field, path in fields.items():
            doc[es_field] = anno.path(path)

        artworks = extract_artworks(container, overlap_query)
        logger.trace(" - artworks: {}", artworks)
        for lang in artworks.keys():
            lang_key = f"artworks{lang.upper()}"
            doc[lang_key] = sorted(artworks[lang])

        persons = extract_persons(container, overlap_query)
        logger.trace(" - persons: {}", persons)
        doc['persons'] = sorted(persons)

        for view in views:
            view_name = f"{view["name"]}Text"
            for constraint in view["constraints"]:
                overlap_query[constraint["path"]] = constraint["value"]
            logger.trace(" - overlap query: {}", overlap_query)
            overlap_search: SearchResultAdapter = SearchResultAdapter(
                container, overlap_query
            )
            try:
                overlap_anno = next(overlap_search.items())
                logger.trace(" - overlap_anno: {}", overlap_anno)

                text_target = overlap_anno.first_target_without_selector("LogicalText")
                resp = requests.get(text_target["source"], timeout=5)
                if resp.status_code != 200:
                    logger.warning(
                        "Failed to get text for {}: {}",
                        overlap_anno.path("body.id"),
                        resp,
                    )
                else:
                    view_text = "".join(resp.json())
                    logger.trace(f" - {view_name}=[{view_text}]")
                    doc[view_name] = view_text

            except StopIteration:
                logger.warning(f"Empty '{view["name"]}' view")

        logger.debug(" - es_doc[{}]: {}", doc_id, doc)
        if store_document(elastic, index, doc_id, doc) < 0:
            return -3

    return 0


def main(
        ar_host: str,
        ar_container: str,
        es_host: str,
        es_index: str,
        cfg_path=None,
        show_progress: bool = False,
        log_file_path: str = None,
) -> int:
    if not show_progress:
        logger.remove()
        logger.add(sys.stdout, level="WARNING")

    if log_file_path:
        logger.remove()
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
        logger.add(log_file_path)

    path = CONFIG_DEFAULT if cfg_path is None else cfg_path
    try:
        with open(path, "r", encoding="utf-8") as file:
            conf = yaml.safe_load(file)
    except OSError:
        return -1

    print(f"Indexing {ar_host}/{ar_container} to {es_host}/{es_index}")
    annorepo = AnnoRepoClient(ar_host)
    container = annorepo.container_adapter(ar_container)
    logger.info("AnnoRepo: {about}", about=annorepo.get_about())

    elastic = Elasticsearch(es_host)
    logger.info("ElasticSearch: {info}", info=elastic.info())

    es_result = reset_index(elastic, es_index, MAPPING_FILE)
    if es_result != 0:
        return es_result

    return index_views(
        container,
        elastic,
        es_index,
        query={"body.type": conf["topTier"]},
        fields=conf["fields"],
        views=conf["views"],
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

    try:
        with open(args.config, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            status = main(
                args.annorepo_host,
                args.annorepo_container,
                args.elastic_host,
                args.elastic_index,
                config,
            )
    except OSError:
        status = -1

    sys.exit(status)
