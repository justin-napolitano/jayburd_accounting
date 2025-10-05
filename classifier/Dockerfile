FROM python:3.12-slim
RUN pip install --no-cache-dir psycopg[binary]==3.2.1 pyyaml==6.0.2
WORKDIR /app
COPY classify.py /app/classify.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/classify.py"]
