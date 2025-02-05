FROM python:alpine3.21

COPY requirements.txt .
COPY index.py .
COPY SearchResultAdapter.py .
COPY SearchResultItem.py .
COPY mapping.json .
COPY config.yml .
COPY run.sh .

RUN pip install -r requirements.txt

CMD ["./run.sh"]
