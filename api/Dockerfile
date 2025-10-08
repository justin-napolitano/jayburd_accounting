# api/Dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 \
    psycopg[binary]==3.2.1 \
    python-dateutil==2.9.0.post0

WORKDIR /app
COPY app.py /app/app.py

ENV PYTHONUNBUFFERED=1
# Container listens on 8000. Compose maps host:container (e.g. 8010:8000).
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
