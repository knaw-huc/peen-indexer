import os
import yaml
from pathlib import Path

import requests
from annorepo.client import AnnoRepoClient, ContainerAdapter
from elasticsearch import Elasticsearch
from tqdm import tqdm

from SearchResultAdapter import SearchResultAdapter
from SearchResultItem import SearchResultItem

MAPPING_FILE = 'mapping.json'

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

    anno_count = 0
    # pbar = tqdm(overlapping_anno_search.items(), total=overlapping_anno_search.hits(), colour='blue', leave=True,
    #             unit="ann", bar_format=tqdm_bar_format)
    for anno in overlapping_anno_search.items():
        # pbar.set_description(f'ann: {anno.path('body.id')[13:-37]:>60}')
        item_annos[anno.path('body.type')].append(anno)
        anno_count += 1

    # AnnoRepo now uses a MongoDB Cursor and has no support for upfront 'size' counting anymore
    # assert anno_count == overlapping_anno_search.hits()

    # print(f'item_annos: {item_annos}')
    return item_annos


def fetch_top_tier_text(anno: SearchResultItem):
    text_target = anno.first_target_without_selector('LogicalText')
    r = requests.get(text_target['source'])
    if r.status_code == 200:
        return r.json()
    else:
        print(f'Failed to get text for: {anno.path('body.id')}')
        return {}


def store_document(elastic: Elasticsearch, index: str, doc: dict[str, any]) -> None:
    doc_id = doc['id']
    resp = elastic.index(index=index, id=doc_id, document=doc)
    if resp['result'] == 'created':
        print(f'Indexed {doc_id}: {len(doc.get('entityNames',[]))} entities')
    else:
        print(f'Indexing {doc_id} failed: {resp}')


def index_suriano(container: ContainerAdapter, elastic: Elasticsearch, index: str, query: Query,
                  fields: dict[str, str]) -> None:
    top_tier_anno_search: SearchResultAdapter = SearchResultAdapter(container, query)
    for anno in top_tier_anno_search.items():
        doc = dict()
        doc['id'] = anno.path('body.id')
        doc['text'] = "".join(fetch_top_tier_text(anno))
        for es_field, path in fields.items():
            doc[es_field] = anno.path(path)

        names = index_overlapping_annotations(container, anno)
        if names:
            doc['entityNames'] = names

        store_document(elastic, index, doc)


def index_overlapping_annotations(container: ContainerAdapter, anno: SearchResultItem):
    overlapping_annos = fetch_overlapping_annotations(container, anno, ['tf:Ent'])

    # collect all entity names into set to deduplicate possible multiples
    entity_names = set()
    for ent in overlapping_annos['tf:Ent']:
        name = ent.path('body.metadata.details[0].value')
        if name:
            entity_names.add(name)
        else:
            print(f'WARN: no name found for: {ent.path('body.metadata.entityId')}')

    return list(entity_names)


def main(ar_host: str, ar_container: str, es_host: str, es_index: str, conf: any) -> None:
    print(f'Indexing {ar_host}/{ar_container} to {es_host}/{es_index}')
    annorepo = AnnoRepoClient(ar_host)
    container = annorepo.container_adapter(ar_container)
    print(annorepo.get_about(), container)

    elastic = Elasticsearch(es_host)
    print(elastic.info())
    reset_index(elastic, es_index, MAPPING_FILE)

    index_suriano(container, elastic, es_index, {"body.type": "LetterBody"}, conf["fields"])


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
    parser.add_argument('--config', metavar='path', required=False,
                        default='config.yml', help='configuration file')
    args = parser.parse_args()

    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)
        main(args.annorepo_host, args.annorepo_container, args.elastic_host, args.elastic_index, config)
