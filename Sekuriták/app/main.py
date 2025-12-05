from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.router import router

app = FastAPI(title="Security Agent UI + API")

# Statické soubory (js, css, obrázky)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# HTML šablony
templates = Jinja2Templates(directory="app/templates")

# Připojíme router s HTML + API
app.include_router(router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
