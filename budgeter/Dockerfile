FROM python:3.12-slim
RUN pip install --no-cache-dir psycopg[binary]==3.2.1 python-dateutil==2.9.0.post0 pyyaml==6.0.2
WORKDIR /app
COPY budget_import.py /app/budget_import.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/budget_import.py"]
