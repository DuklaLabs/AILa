# ---------- Portálový shell (React, třetí build v UI/) ----------
FROM node:20 AS portal-ui
WORKDIR /ui
COPY UI/package*.json ./
RUN npm ci
COPY UI/ ./
# Shared brand palette/fonts (see Shared/webui/theme.css) — single source for
# all apps. scripts/sync-theme.mjs (run by the npm pre* hooks below) copies
# it into src/theme.css; it expects it as a sibling of UI/, hence /Shared/...
COPY Shared/webui/theme.css Shared/webui/theme-toggle.js Shared/webui/ui.css Shared/webui/ui.js /Shared/webui/
RUN npm run build:portal && cp dist-portal/index.portal.html dist-portal/index.html
# -> /ui/dist-portal (Vite base=/). Vite names the entry after its input file
# (index.portal.html, to not collide with the RBAC/Projects builds' own entry
# points during `npm run build:*`); Caddy's file_server expects index.html.


# ---------- reverse proxy ----------
FROM caddy:2-alpine

COPY Gateway/Caddyfile /etc/caddy/Caddyfile
COPY --from=portal-ui /ui/dist-portal /srv/portal
# Statické moduly (bare-skeleton stránky): /vyuka/, /rocnikove-prace/ ...
COPY Gateway/modules/ /srv/portal/
# Sdílené UI (jediný zdroj pravdy je Shared/webui) pro statické moduly
COPY Shared/webui/theme.css Shared/webui/ui.css Shared/webui/ui.js Shared/webui/theme-toggle.js /srv/portal/shared/

EXPOSE 80
