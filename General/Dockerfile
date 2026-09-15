FROM python:3.11-slim

WORKDIR /app

# Viz AccessRequest/Dockerfile: školní/firemní proxy s HTTPS inspekcí rozbíjí
# pip cert check i uvnitř kontejneru. --trusted-host to pro PyPI vypne –
# ok pro lokální dev/lab image.
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

# Shared/ailacore je sourozenecký adresář – build context musí být kořen repa
# (viz docker-compose.yml `context: .` pro tuto službu).
COPY Shared /shared
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e /shared

COPY General/requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY General/ .

EXPOSE 8008

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
