from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routers import auth, workspaces, channels, messages, invitations

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(channels.router)
app.include_router(messages.router)
app.include_router(invitations.router)

@app.get("/")
def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})