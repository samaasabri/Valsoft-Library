from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from sqlmodel import Session, func, select

from ..db import get_session
from ..deps import current_user, require_admin
from ..models import Book, Loan, User
from ..templating import templates

router = APIRouter()


def _search_books(
    session: Session,
    q: Optional[str] = None,
    genre: Optional[str] = None,
    author: Optional[str] = None,
    available_only: bool = False,
    limit: Optional[int] = None,
) -> list[Book]:
    stmt = select(Book)
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Book.title).like(pattern),
                func.lower(Book.author).like(pattern),
                func.lower(func.coalesce(Book.tags, "")).like(pattern),
                func.lower(func.coalesce(Book.isbn, "")).like(pattern),
                func.lower(func.coalesce(Book.summary, "")).like(pattern),
            )
        )
    if genre:
        stmt = stmt.where(func.lower(Book.genre) == genre.lower())
    if author:
        stmt = stmt.where(func.lower(Book.author).like(f"%{author.lower()}%"))
    if available_only:
        stmt = stmt.where(Book.available_copies > 0)
    stmt = stmt.order_by(Book.title)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.exec(stmt))


def _all_genres(session: Session) -> list[str]:
    rows = session.exec(select(Book.genre).where(Book.genre.is_not(None)).distinct()).all()
    return sorted({g for g in rows if g})


@router.get("/books", response_class=HTMLResponse)
def list_books(
    request: Request,
    q: Optional[str] = None,
    genre: Optional[str] = None,
    author: Optional[str] = None,
    available_only: bool = False,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(current_user),
):
    books = _search_books(
        session, q=q, genre=genre, author=author, available_only=available_only
    )
    active_loans = {}
    if user:
        loans = session.exec(
            select(Loan).where(Loan.user_id == user.id, Loan.returned_at.is_(None))
        ).all()
        active_loans = {l.book_id: l for l in loans}

    ctx = {
        "request": request,
        "user": user,
        "books": books,
        "q": q or "",
        "genre": genre or "",
        "author": author or "",
        "available_only": available_only,
        "genres": _all_genres(session),
        "active_loans": active_loans,
    }
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse("books/_grid.html", ctx)
    return templates.TemplateResponse("books/list.html", ctx)


@router.get("/books/new", response_class=HTMLResponse)
def new_book_form(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse(
        "books/form.html",
        {"request": request, "user": user, "book": None, "mode": "create"},
    )


@router.post("/books/new")
def create_book(
    request: Request,
    title: str = Form(...),
    author: str = Form(...),
    isbn: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    published_year: Optional[int] = Form(None),
    summary: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    cover_url: Optional[str] = Form(None),
    total_copies: int = Form(1),
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    if total_copies < 1:
        total_copies = 1
    book = Book(
        title=title.strip(),
        author=author.strip(),
        isbn=(isbn or None),
        genre=(genre or None),
        published_year=published_year,
        summary=(summary or None),
        tags=(tags or ""),
        cover_url=(cover_url or None),
        total_copies=total_copies,
        available_copies=total_copies,
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return RedirectResponse(
        url=f"/books?flash=Added+%22{book.title}%22", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/books/{book_id}/edit", response_class=HTMLResponse)
def edit_book_form(
    book_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return templates.TemplateResponse(
        "books/form.html",
        {"request": request, "user": user, "book": book, "mode": "edit"},
    )


@router.post("/books/{book_id}/edit")
def update_book(
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    isbn: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    published_year: Optional[int] = Form(None),
    summary: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    cover_url: Optional[str] = Form(None),
    total_copies: int = Form(1),
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if total_copies < 1:
        total_copies = 1
    on_loan = book.total_copies - book.available_copies
    book.title = title.strip()
    book.author = author.strip()
    book.isbn = isbn or None
    book.genre = genre or None
    book.published_year = published_year
    book.summary = summary or None
    book.tags = tags or ""
    book.cover_url = cover_url or None
    book.total_copies = total_copies
    book.available_copies = max(0, total_copies - on_loan)
    session.add(book)
    session.commit()
    return RedirectResponse(
        url=f"/books?flash=Updated+%22{book.title}%22", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/books/{book_id}/delete")
def delete_book(
    book_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    open_loans = session.exec(
        select(Loan).where(Loan.book_id == book_id, Loan.returned_at.is_(None))
    ).first()
    if open_loans:
        return RedirectResponse(
            url="/books?flash=Cannot+delete+a+book+with+active+loans",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    session.delete(book)
    session.commit()
    return RedirectResponse(
        url=f"/books?flash=Deleted+%22{book.title}%22", status_code=status.HTTP_303_SEE_OTHER
    )
