FROM python:3.11-slim

WORKDIR /app

# Shared/ailacore is a sibling directory — build context must be the repo
# root. In docker-compose.yml, set this service's build to:
#   build:
#     context: .
#     dockerfile: <YourService>/Dockerfile
# Some networks (school/corporate proxy, antivirus with HTTPS scanning, VPN)
# MITM outbound HTTPS with a root CA trusted on the host but not inside this
# container, so pip's cert check fails even though PyPI is reachable.
# --trusted-host skips that check — fine for a local dev/lab image.
COPY Shared /shared
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e /shared

COPY Template/requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY Template/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
