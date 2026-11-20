FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential && apt-get clean

# Viz AccessRequest/Dockerfile: školní/firemní proxy s HTTPS inspekcí rozbíjí
# pip cert check i uvnitř kontejneru. --trusted-host to pro PyPI vypne –
# ok pro lokální dev/lab image.
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

# Shared/ailacore je sourozenecký adresář – build context musí být kořen repa
# (viz docker-compose.yml `context: .` pro tuto službu).
COPY Shared /shared
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e /shared

COPY "Skladník/requirements.txt" .

RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY "Skladník/" .

# Shared brand palette + UI library (see Shared/webui/) — single source for all
# apps, copied in rather than duplicated in sklad.css.
COPY Shared/webui/theme.css app/static/theme.css
COPY Shared/webui/ui.css Shared/webui/ui.js Shared/webui/theme-toggle.js app/static/

RUN mkdir -p /app/data

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]