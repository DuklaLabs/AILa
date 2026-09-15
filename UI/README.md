# UI

Jeden React (Vite) projekt, ze kterého se stavějí **dvě nezávislé SPA** —
sdílí `package.json`/závislosti, ale mají oddělený vstupní bod, Vite config
i výstupní adresář a mountuje/servíruje je pokaždé jiná backend služba na
jiné cestě (kvůli cookie session `dl_session` musí SPA i API sedět na
stejném originu).

| SPA | Vstupní bod | Vite config | `base` / cesta | Servíruje | Build příkaz |
|---|---|---|---|---|---|
| RBAC admin konzole | `src/main.jsx` → `src/App.jsx` → `src/rbac/RbacConsole.jsx` | `vite.config.js` | `/admin/rbac/` | `ailacore.admin.mount_admin_ui` (kterákoli služba, co si ji zamountuje — dnes `AccessRequest`) | `npm run build` → `dist/` |
| Projekty | `src/projects/main.jsx` → `ProjectsApp.jsx` | `vite.projects.config.js` (`outDir: dist-projects`, `input: index.projects.html`) | `/app/projects/` | `Projects` server přes `ailacore.admin.mount_spa` | `npm run build:projects` → `dist-projects/` |

`src/LabOrchestratorDashboard.jsx`(`.css`) zůstává v repu, ale nic ho
neimportuje (`App.jsx` teď rovnou rendruje `RbacConsole`) — mrtvý kód,
ne aktivní třetí SPA.

## RBAC admin konzole (`src/rbac/`)

Správa RBAC jádra (`ailacore`): katalog oprávnění, mapování role →
oprávnění, přiřazení rolí a přímých grantů uživatelům, audit změn.

- `RbacConsole.jsx` — root komponenta, taby.
- `panels/PermissionsPanel.jsx`, `RolesPanel.jsx`, `UsersPanel.jsx`,
  `AuditPanel.jsx` — jeden panel na tab.
- `api.js` — klient nad `/api/rbac/...` (viz `Shared/README.md`).

## Projekty (`src/projects/`)

Frontend k `Projects/` serveru (port 8006) — nástěnka/Gantt projektového
systému, viz `Projects/README.md` pro backend a RBAC.

- `ProjectsApp.jsx` — root komponenta: identita (`api.me()`), přepínač
  Nástěnka/Timeline, postranní panel se stromem projektů, drawer úkolu.
- `panels/ProjectTree.jsx` — workspace → složka → projekt strom.
- `panels/BoardView.jsx` — kanban podle stavu (semaforu).
- `panels/GanttView.jsx` — timeline s závislostmi.
- `panels/TaskDrawer.jsx` — detail/editace úkolu.
- `panels/CostSummary.jsx` — finanční součet projektu (`projects.finance:read`).
- `panels/ProposalsPanel.jsx` — schvalování AI návrhů (`projects.proposal:review`).
- `panels/PocketPanel.jsx` — nahrávání/upload schůzky na Pocket, extrakce
  kandidátních úkolů, potvrzení jako proposal (`projects.ai:use`).
- `panels/TimerPanel.jsx` — běžící stopky (time tracking).
- `api.js` — klient nad `/api/...` Projects serveru + `can(perms, name)`
  helper nad polem oprávnění z `api.me()`.

## Vývoj

```
npm install

npm run dev             # RBAC konzole — http://localhost:5173/admin/rbac/
npm run dev:projects    # Projekty     — http://localhost:5173/app/projects/
```

Každý dev server proxuje `/api/*` na svůj backend (`vite.config.js` →
`:8003` access-request-server, `vite.projects.config.js` → `:8006`
projects-server), přepsatelné přes `VITE_API_TARGET`. Backend musí běžet
zvlášť; přihlas se ve druhém tabu na `/login` daného backendu — session
cookie platí i pro dev server přes proxy.

## Build

```
npm run build            # -> dist/           (RBAC konzole, base=/admin/rbac/)
npm run build:projects   # -> dist-projects/  (Projekty,     base=/app/projects/)
```

`dist/` kopíruje do image `AccessRequest/Dockerfile` (stage `rbac-ui`) tam,
kam ukazuje `RBAC_UI_DIST`. `dist-projects/` kopíruje `Projects/Dockerfile`
(stage `projects-ui`) analogicky. `npm run lint` (ESLint) a `npm run
preview` fungují nad libovolným posledním buildem.
