# ---------- Projects SPA (React, druhý build v UI/) ----------
FROM node:20 AS projects-ui
WORKDIR /ui
COPY UI/package*.json ./
RUN npm ci
COPY UI/ ./
RUN npm run build:projects     # -> /ui/dist-projects (Vite base=/app/projects/)


# ---------- aplikace ----------
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

COPY Projects/requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY Projects/ .

# buildnutá SPA – ailacore.admin.mount_spa ji hledá v PROJECTS_UI_DIST
COPY --from=projects-ui /ui/dist-projects /app/projects-ui-dist

EXPOSE 8006

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
