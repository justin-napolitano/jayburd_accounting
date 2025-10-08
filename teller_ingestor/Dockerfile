FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests==2.32.3 psycopg[binary]==3.2.1 python-dateutil==2.9.0.post0

WORKDIR /app
COPY teller_ingestor.py /app/teller_ingestor.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/teller_ingestor.py"]
