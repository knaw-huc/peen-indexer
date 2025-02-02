import collections
import gzip
import logging
import traceback
from pathlib import Path
from typing import List, Dict, Any

import jsonpickle
import requests
from annorepo.client import AnnoRepoClient, ContainerAdapter
from elasticsearch import Elasticsearch
from tqdm import tqdm

#from SearchResultAdapter import SearchResultAdapter
#from SearchResultItem import SearchResultItem
#from SparseList import SparseList

annorepo = AnnoRepoClient('https://annorepo.suriano.huygens.knaw.nl')
container = annorepo.container_adapter('suriano-1.0.1e-029')
print(annorepo.get_about())
