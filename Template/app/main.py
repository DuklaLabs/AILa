from fastapi import FastAPI

from ailacore.db import close_pool

from app.router import router

app = FastAPI(title="Název agenta")
app.include_router(router)

# Volitelně: sdílená RBAC administrace (API + React konzole na /admin/rbac/).
# Dockerfile služby musí buildnout UI/ a nakopírovat dist tam, kam ukazuje
# RBAC_UI_DIST (viz AccessRequest/Dockerfile stage `rbac-ui`).
#
# import os
# from ailacore.admin import rbac_api_router, mount_admin_ui
# app.include_router(rbac_api_router)
# mount_admin_ui(app, os.getenv("RBAC_UI_DIST", "rbac-ui-dist"))


@app.on_event("shutdown")
async def _shutdown():
    await close_pool()


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
