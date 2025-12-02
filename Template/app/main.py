from fastapi import FastAPI
from app.router import router

app = FastAPI(title="Název agenta")
app.include_router(router)