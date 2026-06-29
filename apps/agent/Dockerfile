FROM python:3.11-slim

WORKDIR /app

COPY apps/agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/agent/src /app/src
COPY apps/agent/servers.json /app/servers.json

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
