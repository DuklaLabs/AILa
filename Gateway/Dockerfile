# ---------- Portálový shell (React, třetí build v UI/) ----------
FROM node:20 AS portal-ui
WORKDIR /ui
COPY UI/package*.json ./
RUN npm ci
COPY UI/ ./
RUN npm run build:portal && cp dist-portal/index.portal.html dist-portal/index.html
# -> /ui/dist-portal (Vite base=/). Vite names the entry after its input file
# (index.portal.html, to not collide with the RBAC/Projects builds' own entry
# points during `npm run build:*`); Caddy's file_server expects index.html.


# ---------- reverse proxy ----------
FROM caddy:2-alpine

COPY Gateway/Caddyfile /etc/caddy/Caddyfile
COPY --from=portal-ui /ui/dist-portal /srv/portal

EXPOSE 80
