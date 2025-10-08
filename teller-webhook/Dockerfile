FROM python:3.12-slim
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn[standard]==0.30.6 psycopg[binary]==3.2.1
WORKDIR /app
COPY webhook.py /app/webhook.py
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "webhook:app", "--host", "0.0.0.0", "--port", "8081"]

