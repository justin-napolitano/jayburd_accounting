FROM python:3.12-slim
RUN pip install --no-cache-dir psycopg[binary]==3.2.1 python-dateutil==2.9.0.post0 pandas==2.2.2 chardet==5.2.0 ofxparse==0.21
WORKDIR /app
COPY normalizer.py /app/normalizer.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/normalizer.py"]

