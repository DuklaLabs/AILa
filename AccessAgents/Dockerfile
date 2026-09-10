FROM python:3.11-slim

WORKDIR /app

# Shared/ailacore je sourozenecký adresář — build kontext musí být kořen repa.
# V docker-compose.yml:
#   build:
#     context: .
#     dockerfile: AccessAgents/Dockerfile
COPY Shared /shared
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e /shared

COPY AccessAgents/requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY AccessAgents/ .

EXPOSE 8007

CMD ["python", "app/run.py"]
