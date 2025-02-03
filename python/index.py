import collections
import gzip
import logging
import os
import traceback
from pathlib import Path

import jsonpickle
import requests
from annorepo.client import AnnoRepoClient, ContainerAdapter, SearchInfo
from elasticsearch import Elasticsearch
from tqdm import tqdm

from SearchResultAdapter import SearchResultAdapter
from SearchResultItem import SearchResultItem
#from SparseList import SparseList

MAPPING_FILE='mapping.json'

type Query = dict[str, str]

def reset_index(elastic: Elasticsearch, index_name: str, path: str | os.PathLike) -> None:
    if elastic.indices.exists(index=index_name):
        print(f'Deleting ES index: {index_name}')
        elastic.indices.delete(index=index_name)

    mapping_path = Path(path)
    print(f'Creating ES index: {index_name} using mapping from {mapping_path}')
    elastic.indices.create(index=index_name, body=mapping_path.read_text())

def build_overlapping_types_query(item: SearchResultItem, types: list[str]) -> dict[str, any]:
    target = item.first_target_with_selector('Text')
    selector = target['selector']
    return {"body.type": {":isIn": types},
            ":overlapsWithTextAnchorRange": {
                "source": target['source'],
                "start": selector['start'],
                "end": selector['end']
            }}

def fetch_overlapping_annotations(container: ContainerAdapter, item: SearchResultItem, types: list[str]) \
        -> dict[str, list[SearchResultItem]]:
    query = build_overlapping_types_query(item, types)

    item_annos = dict()
    for t in types:
        item_annos[t] = list()

    overlapping_anno_search = SearchResultAdapter(container, query)
    print(query)
    print(overlapping_anno_search.search_info)

    anno_count = 0
    # pbar = tqdm(overlapping_anno_search.items(), total=overlapping_anno_search.hits(), colour='blue', leave=True,
    #             unit="ann", bar_format=tqdm_bar_format)
    for anno in overlapping_anno_search.items():
        # pbar.set_description(f'ann: {anno.path('body.id')[13:-37]:>60}')
        item_annos[anno.path('body.type')].append(anno)
        anno_count += 1

    # AnnoRepo now uses a MongoDB Cursor and has no support for upfront 'size' counting anymore
    # assert anno_count == overlapping_anno_search.hits()

    print(f'item_annos: {item_annos}')
    return item_annos

def index_suriano(container:ContainerAdapter, elastic:Elasticsearch, query: Query) -> None:
    fields = {
        'bodyType': 'body.type',
        'date': 'body.metadata.date',
        'editorNotes': 'body.metadata.editorNotes',
        'recipient': 'body.metadata.recipient',
        'recipientLoc': 'body.metadata.recipientLoc',
        'sender': 'body.metadata.sender',
        'senderLoc': 'body.metadata.senderLoc',
        'shelfmark': 'body.metadata.shelfmark',
        'summary': 'body.metadata.summary',
    }
    top_tier_anno_search: SearchResultAdapter = SearchResultAdapter(container, query)
    for anno in top_tier_anno_search.items():
        doc = dict()
        doc['id'] = anno.path('body.id')
        for es_field, path in fields.items():
            doc[es_field] = anno.path(path)
        print(f'doc: {doc}')

def index_overlapping_annotations(anno, container):
    overlapping_annos = fetch_overlapping_annotations(container, anno, ['tf:Ent'])
    for i in overlapping_annos['tf:Ent']:
        print(f'i: {i}')


def main(ar_host: str, ar_container: str, es_host: str, es_index) -> None:
    print(f'Indexing {ar_host}/{ar_container} to {es_host}/{es_index}')
    annorepo = AnnoRepoClient(ar_host)
    container = annorepo.container_adapter(ar_container)
    print(annorepo.get_about(), container)

    elastic = Elasticsearch(es_host)
    print(elastic.info())
    reset_index(elastic, es_index, MAPPING_FILE)

    index_suriano(container, elastic, {"body.type": "LetterBody"})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='index annorepo container to elastic index')
    parser.add_argument('--annorepo-host', metavar='path', required=True,
                        help='the AnnoRepo host')
    parser.add_argument('--annorepo-container', metavar='path', required=True,
                        help='the AnnoRepo container on annorepo-host')
    parser.add_argument('--elastic-host', metavar='path', required=False,
                        default='http://localhost:9200', help='the ElasticSearch host name')
    parser.add_argument('--elastic-index', metavar='path', required=True,
                        help='the ElasticSearch index name')
    args=parser.parse_args()
    main(args.annorepo_host, args.annorepo_container, args.elastic_host, args.elastic_index)
