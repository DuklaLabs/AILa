# UI — RBAC admin konzole

React SPA pro správu RBAC jádra (`ailacore`): katalog oprávnění, mapování
role → oprávnění, přiřazení rolí a přímých grantů uživatelům, audit změn.

Servíruje ji `ailacore.admin.mount_admin_ui` pod `/admin/rbac/` na stejném originu
jako API (kvůli cookie session `dl_session`) — ne vlastní kontejner. Vstupní bod je
`src/rbac/RbacConsole.jsx`; orchestrátorský dashboard (`src/LabOrchestratorDashboard.jsx`)
zůstává v repu, ale tenhle build ho nemountuje.

## Vývoj

```
npm install
npm run dev        # http://localhost:5173/admin/rbac/
```

`npm run dev` proxuje `/api/*` na `http://localhost:8003` (běžící `access-request-server`).
Jiný cíl: `VITE_API_TARGET=http://... npm run dev`. Přihlas se ve druhém tabu na
`http://localhost:8003/login` jako admin (`Database/seed_admin.py`) — session cookie
platí i pro dev server přes proxy.

## Build

```
npm run build      # -> dist/  (Vite base = /admin/rbac/)
```

`dist/` se v Dockeru služby nakopíruje tam, kam ukazuje `RBAC_UI_DIST`
(viz stage `rbac-ui` v `AccessRequest/Dockerfile`).
