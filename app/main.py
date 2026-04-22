from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .db import init_db
from .deps import current_user
from .routers import ai, auth, books, loans
from .templating import templates

settings = get_settings()

app = FastAPI(title="Mini Library", docs_url="/docs")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="library_session",
    same_site="lax",
    https_only=False,
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


app.include_router(auth.router)
app.include_router(books.router)
app.include_router(loans.router)
app.include_router(ai.router)


@app.get("/")
def index(request: Request, user=Depends(current_user)):
    return RedirectResponse(url="/books")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(
        "errors/404.html",
        {"request": request, "user": None, "settings": settings},
        status_code=404,
    )
