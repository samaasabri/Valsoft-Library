from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from ..db import get_session
from ..deps import current_user, require_admin, require_user
from ..models import Book, Loan, User
from ..templating import templates

router = APIRouter()

LOAN_DAYS = 14


@router.post("/books/{book_id}/checkout", response_class=HTMLResponse)
def checkout_book(
    book_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    existing = session.exec(
        select(Loan).where(
            Loan.book_id == book_id,
            Loan.user_id == user.id,
            Loan.returned_at.is_(None),
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have this book checked out")

    if book.available_copies <= 0:
        raise HTTPException(status_code=400, detail="No copies available")

    loan = Loan(
        book_id=book.id,
        user_id=user.id,
        due_at=datetime.utcnow() + timedelta(days=LOAN_DAYS),
    )
    book.available_copies -= 1
    session.add(loan)
    session.add(book)
    session.commit()
    session.refresh(book)

    if request.headers.get("HX-Request") == "true":
        active = {book.id: loan}
        return templates.TemplateResponse(
            "books/_card.html",
            {"request": request, "user": user, "book": book, "active_loans": active},
        )
    return RedirectResponse(url="/books", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/loans/{loan_id}/return", response_class=HTMLResponse)
def return_loan(
    loan_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    loan = session.get(Loan, loan_id)
    if not loan or loan.returned_at is not None:
        raise HTTPException(status_code=404, detail="Active loan not found")
    if loan.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your loan")

    book = session.get(Book, loan.book_id)
    loan.returned_at = datetime.utcnow()
    if book:
        book.available_copies = min(book.total_copies, book.available_copies + 1)
        session.add(book)
    session.add(loan)
    session.commit()

    if request.headers.get("HX-Request") == "true":
        if not book:
            return HTMLResponse("")
        session.refresh(book)
        return templates.TemplateResponse(
            "books/_card.html",
            {"request": request, "user": user, "book": book, "active_loans": {}},
        )
    return RedirectResponse(url="/my-loans", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/my-loans", response_class=HTMLResponse)
def my_loans(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    active = session.exec(
        select(Loan, Book)
        .where(Loan.user_id == user.id, Loan.returned_at.is_(None))
        .join(Book, Book.id == Loan.book_id)
        .order_by(Loan.checked_out_at.desc())
    ).all()
    past = session.exec(
        select(Loan, Book)
        .where(Loan.user_id == user.id, Loan.returned_at.is_not(None))
        .join(Book, Book.id == Loan.book_id)
        .order_by(Loan.returned_at.desc())
        .limit(25)
    ).all()
    return templates.TemplateResponse(
        "loans.html",
        {"request": request, "user": user, "active": active, "past": past, "now": datetime.utcnow()},
    )


@router.get("/admin/loans", response_class=HTMLResponse)
def admin_active_loans(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    active = session.exec(
        select(Loan, Book, User)
        .where(Loan.returned_at.is_(None))
        .join(Book, Book.id == Loan.book_id)
        .join(User, User.id == Loan.user_id)
        .order_by(Loan.checked_out_at.desc())
    ).all()
    return templates.TemplateResponse(
        "admin_loans.html",
        {"request": request, "user": user, "active": active, "now": datetime.utcnow()},
    )
