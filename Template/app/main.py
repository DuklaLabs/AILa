from fastapi import FastAPI

from ailacore.db import close_pool

from app.router import router

app = FastAPI(title="Název agenta")
app.include_router(router)


@app.on_event("shutdown")
async def _shutdown():
    await close_pool()


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
