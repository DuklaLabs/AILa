from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.router import router as admin_router
from app.auth import router_auth
from app.students import router_students

from app.open_hours import router as open_hours_router


app = FastAPI()

# statické soubory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# šablony
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Hlavní rozcestník – obsahuje odkazy na login, admin, student dashboard atd.
    """
    return templates.TemplateResponse("index.html", {"request": request})


# připojení routerů
app.include_router(router_auth)
app.include_router(router_students)
app.include_router(admin_router)
app.include_router(open_hours_router)
