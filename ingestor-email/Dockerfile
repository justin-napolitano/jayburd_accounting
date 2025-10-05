FROM python:3.12-slim
RUN pip install --no-cache-dir psycopg[binary]==3.2.1 python-dateutil==2.9.0.post0
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY email_puller.py /app/email_puller.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/email_puller.py"]

