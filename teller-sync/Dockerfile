# teller-sync/Dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir psycopg[binary]==3.2.1 requests==2.32.3 python-dateutil==2.9.0.post0

WORKDIR /app
COPY sync.py /app/sync.py
COPY enroll.py /app/enroll.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/sync.py"]
