from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Session, func, select

from ..db import get_session
from ..deps import current_user, require_user
from ..models import Book, User
from ..services import gemini as gemini_service
from ..templating import templates

router = APIRouter()


class AutofillRequest(BaseModel):
    title: str
    author: str


@router.post("/ai/autofill")
def ai_autofill(
    payload: AutofillRequest,
    user: User = Depends(require_user),
):
    if not payload.title.strip() or not payload.author.strip():
        raise HTTPException(status_code=400, detail="Title and author are required.")
    try:
        data = gemini_service.autofill_book_metadata(payload.title.strip(), payload.author.strip())
    except gemini_service.GeminiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    # Hint a cover URL from Open Library if no cover was selected yet.
    cover_url = None
    kw = data.get("cover_keywords")
    if kw:
        cover_url = f"https://covers.openlibrary.org/b/title/{kw.replace(' ', '+')}-M.jpg"
    return {**data, "cover_url": cover_url}


# ---------- Librarian chat ----------

def _book_to_dict(b: Book) -> Dict[str, Any]:
    return {
        "id": b.id,
        "title": b.title,
        "author": b.author,
        "genre": b.genre,
        "published_year": b.published_year,
        "summary": b.summary,
        "tags": [t.strip() for t in (b.tags or "").split(",") if t.strip()],
        "available_copies": b.available_copies,
        "total_copies": b.total_copies,
        "cover_url": b.cover_url,
    }


def _make_dispatcher(session: Session):
    def search_books(
        query: Optional[str] = None,
        genre: Optional[str] = None,
        author: Optional[str] = None,
        available_only: bool = False,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        stmt = select(Book)
        if query:
            pattern = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Book.title).like(pattern),
                    func.lower(Book.author).like(pattern),
                    func.lower(func.coalesce(Book.tags, "")).like(pattern),
                    func.lower(func.coalesce(Book.summary, "")).like(pattern),
                )
            )
        if genre:
            stmt = stmt.where(func.lower(Book.genre) == genre.lower())
        if author:
            stmt = stmt.where(func.lower(Book.author).like(f"%{author.lower()}%"))
        if available_only:
            stmt = stmt.where(Book.available_copies > 0)
        stmt = stmt.limit(max(1, min(limit or 5, 10)))
        return [_book_to_dict(b) for b in session.exec(stmt)]

    def recommend_similar(title: str, limit: int = 5) -> List[Dict[str, Any]]:
        seed = session.exec(
            select(Book).where(func.lower(Book.title).like(f"%{title.lower()}%"))
        ).first()
        if seed is None:
            return []
        seed_tags = {t.strip().lower() for t in (seed.tags or "").split(",") if t.strip()}
        candidates = session.exec(select(Book).where(Book.id != seed.id)).all()
        scored = []
        for b in candidates:
            score = 0
            if seed.genre and b.genre and seed.genre.lower() == b.genre.lower():
                score += 3
            if seed.author and b.author and seed.author.lower() == b.author.lower():
                score += 2
            b_tags = {t.strip().lower() for t in (b.tags or "").split(",") if t.strip()}
            score += len(seed_tags & b_tags)
            if score > 0:
                scored.append((score, b))
        scored.sort(key=lambda x: (-x[0], x[1].title))
        top = [b for _, b in scored[: max(1, min(limit or 5, 10))]]
        return [_book_to_dict(b) for b in top]

    def dispatch(name: str, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        if name == "search_books":
            return search_books(**args)
        if name == "recommend_similar":
            return recommend_similar(**args)
        return []

    return dispatch


@router.get("/ai/librarian", response_class=HTMLResponse)
def librarian_page(request: Request, user: Optional[User] = Depends(current_user)):
    return templates.TemplateResponse(
        "ai/librarian.html",
        {"request": request, "user": user},
    )


@router.post("/ai/librarian/message", response_class=HTMLResponse)
def librarian_message(
    request: Request,
    message: str = Form(...),
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    message = (message or "").strip()
    if not message:
        return HTMLResponse("")

    user_bubble = templates.get_template("ai/_bubble_user.html").render(
        {"request": request, "message": message}
    )

    try:
        result = gemini_service.librarian_reply(message, _make_dispatcher(session))
        ai_bubble = templates.get_template("ai/_bubble_ai.html").render(
            {
                "request": request,
                "reply": result["reply"] or "Here's what I found:",
                "books": result["books"],
            }
        )
    except gemini_service.GeminiUnavailable as e:
        ai_bubble = templates.get_template("ai/_bubble_ai.html").render(
            {
                "request": request,
                "reply": f"AI is unavailable: {e}",
                "books": [],
            }
        )

    return HTMLResponse(user_bubble + ai_bubble)
