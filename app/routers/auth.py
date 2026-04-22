import logging
from typing import Optional

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

logger = logging.getLogger("app.auth")

from ..config import get_settings
from ..db import get_session
from ..models import User
from ..templating import templates

router = APIRouter()
settings = get_settings()

oauth = OAuth()
if settings.google_sso_enabled:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _upsert_user(session: Session, email: str, name: str = "", picture_url: str = "") -> User:
    email = email.lower().strip()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        role = "admin" if email in settings.admin_emails else "member"
        user = User(email=email, name=name or email.split("@")[0], picture_url=picture_url, role=role)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    changed = False
    if name and user.name != name:
        user.name = name
        changed = True
    if picture_url and user.picture_url != picture_url:
        user.picture_url = picture_url
        changed = True
    if email in settings.admin_emails and user.role != "admin":
        user.role = "admin"
        changed = True
    if changed:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _safe_next(next_url: Optional[str]) -> str:
    target = (next_url or "").strip()
    # Allow only local absolute paths to avoid open redirects.
    if target.startswith("/") and not target.startswith("//"):
        return target
    return "/books"


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: Optional[str] = "/books"):
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "user": None,
            "next": next,
            "google_enabled": settings.google_sso_enabled,
            "admin_emails": settings.admin_emails,
        },
    )


@router.get("/auth/google")
async def auth_google(request: Request, next: Optional[str] = "/books"):
    if not settings.google_sso_enabled:
        raise HTTPException(status_code=503, detail="Google SSO not configured")
    # Clear any stale OAuth state entries so repeated login clicks don't
    # accumulate and cause mismatching_state on the next callback.
    for key in [k for k in list(request.session.keys()) if k.startswith("_state_google_")]:
        request.session.pop(key, None)
    request.session["post_login_next"] = _safe_next(next)
    redirect_uri = f"{settings.app_base_url.rstrip('/')}/auth/callback"
    logger.warning(
        "auth_google start host=%s redirect_uri=%s session_keys=%s cookies=%s",
        request.url.hostname,
        redirect_uri,
        list(request.session.keys()),
        list(request.cookies.keys()),
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request, session: Session = Depends(get_session)):
    if not settings.google_sso_enabled:
        raise HTTPException(status_code=503, detail="Google SSO not configured")
    logger.warning(
        "auth_callback host=%s query_state=%s session_keys=%s cookie_names=%s",
        request.url.hostname,
        request.query_params.get("state"),
        list(request.session.keys()),
        list(request.cookies.keys()),
    )
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.warning("OAuth error during callback: %s", e.error)
        hint = ""
        if e.error == "mismatching_state":
            hint = (
                " — session cookie was not returned. Make sure you open the app at the same host "
                "as APP_BASE_URL (no mix of localhost / 127.0.0.1), clear cookies, and try once."
            )
        raise HTTPException(status_code=400, detail=f"OAuth error: {e.error}{hint}")
    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email")
    user = _upsert_user(
        session,
        email=email,
        name=userinfo.get("name", ""),
        picture_url=userinfo.get("picture", ""),
    )
    request.session["user_id"] = user.id
    next_url = _safe_next(request.session.pop("post_login_next", "/books"))
    return RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/auth/dev")
def auth_dev(
    request: Request,
    email: str = Form(...),
    name: Optional[str] = Form(""),
    next: Optional[str] = Form("/books"),
    session: Session = Depends(get_session),
):
    """Dev-login fallback so reviewers can test without Google credentials.

    Uses the same ADMIN_EMAILS promotion logic as real SSO.
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    user = _upsert_user(session, email=email, name=name or "")
    request.session["user_id"] = user.id
    return RedirectResponse(url=_safe_next(next), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/books", status_code=status.HTTP_303_SEE_OTHER)
