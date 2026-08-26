FROM python:3.11-slim

WORKDIR /app

# Some networks (school/corporate proxy, antivirus with HTTPS scanning, VPN)
# MITM outbound HTTPS with a root CA that's trusted on the host but not
# inside this container's Linux VM, so pip's cert check fails even though
# the packages are reachable. --trusted-host (below) skips that check for
# PyPI specifically; the env var covers pip's isolated build-dependency
# subprocess too. Fine for a local dev/lab image, not a public-facing one.
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

# Shared/ailacore is a sibling directory — build context must be the repo
# root (see docker-compose.yml's `context: .` for this service).
COPY Shared /shared
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e /shared

COPY AccessRequest/requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY AccessRequest/ .

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
