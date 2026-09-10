from fastapi import FastAPI
from app.router import router

app = FastAPI(title="Messenger – e-mail (Microsoft Graph)")
app.include_router(router)
