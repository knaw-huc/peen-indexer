FROM python:alpine3.21

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY index.py .
COPY SearchResultAdapter.py .
COPY SearchResultItem.py .
COPY mapping.json .
COPY config.yml .
COPY run.sh .

CMD ["./run.sh"]
