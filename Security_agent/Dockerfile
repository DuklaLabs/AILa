FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy full app folder into container
COPY . /app

# Environment vars
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_HOST=http://ollama:11434

# ENTRYPOINT – run scheduler inside "app/" folder
EXPOSE 8004
CMD ["python", "app/run_agent_service.py"]