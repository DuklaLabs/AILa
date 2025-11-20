FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY postgres_mcp_server.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "postgres_mcp_server.py"]
