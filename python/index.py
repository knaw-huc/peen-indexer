import collections
import gzip
import logging
import os
import traceback
from pathlib import Path
from typing import List, Dict, Any

import jsonpickle
import requests
from annorepo.client import AnnoRepoClient, ContainerAdapter
from elasticsearch import Elasticsearch
from tqdm import tqdm

from SearchResultAdapter import SearchResultAdapter
from SearchResultItem import SearchResultItem
#from SparseList import SparseList

def reset_index(elastic: Elasticsearch, index_name: str, path: str | os.PathLike):
    mapping_path = Path(path)

    if elastic.indices.exists(index=index_name):
        print(f'Deleting ES index: {index_name}')
        elastic.indices.delete(index=index_name)

    print(f'Creating ES index: {index_name} using mapping from {mapping_path}')
    elastic.indices.create(index=index_name, body=mapping_path.read_text())

def main(ar_host: str, ar_container: str, es_host: str, es_index):
    print(f'Indexing {ar_host}/{ar_container} to {es_host}/{es_index}')
    annorepo = AnnoRepoClient(ar_host)
    container = annorepo.container_adapter(ar_container)
    print(annorepo.get_about())

    elastic = Elasticsearch(es_host)
    print(elastic.info())
    reset_index(elastic, es_index, 'mapping.json')


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
