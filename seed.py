"""Seed the database with demo books and an admin user.

Usage:
    python seed.py
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine, init_db
from app.models import Book, User

DEMO_BOOKS = [
    {
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "isbn": "9780547928227",
        "genre": "Fantasy",
        "published_year": 1937,
        "summary": "A reluctant hobbit joins dwarves on a quest to reclaim a mountain from a dragon.",
        "tags": "classic,adventure,dragons",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780547928227-M.jpg",
        "total_copies": 3,
    },
    {
        "title": "1984",
        "author": "George Orwell",
        "isbn": "9780451524935",
        "genre": "Dystopian",
        "published_year": 1949,
        "summary": "A chilling vision of a totalitarian future where Big Brother watches everyone.",
        "tags": "classic,political,dystopia",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780451524935-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "isbn": "9780141439518",
        "genre": "Romance",
        "published_year": 1813,
        "summary": "Elizabeth Bennet navigates manners, morality and marriage in Regency England.",
        "tags": "classic,romance,society",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780141439518-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "isbn": "9780061120084",
        "genre": "Fiction",
        "published_year": 1960,
        "summary": "A young girl in the American South watches her father defend a Black man wrongly accused.",
        "tags": "classic,justice,coming-of-age",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780061120084-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565",
        "genre": "Fiction",
        "published_year": 1925,
        "summary": "A mysterious millionaire chases a lost love across the glittering Jazz Age.",
        "tags": "classic,american,tragedy",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780743273565-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "Brave New World",
        "author": "Aldous Huxley",
        "isbn": "9780060850524",
        "genre": "Dystopian",
        "published_year": 1932,
        "summary": "A pleasure-engineered future where freedom has been traded for comfort.",
        "tags": "classic,dystopia,philosophy",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780060850524-M.jpg",
        "total_copies": 1,
    },
    {
        "title": "Dune",
        "author": "Frank Herbert",
        "isbn": "9780441172719",
        "genre": "Science Fiction",
        "published_year": 1965,
        "summary": "Political intrigue and mysticism on a desert planet that holds the universe's most precious resource.",
        "tags": "sci-fi,epic,politics",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780441172719-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "The Name of the Wind",
        "author": "Patrick Rothfuss",
        "isbn": "9780756404741",
        "genre": "Fantasy",
        "published_year": 2007,
        "summary": "A gifted young man recounts the story of becoming the most notorious wizard of his age.",
        "tags": "fantasy,magic,music",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780756404741-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "The Girl with the Dragon Tattoo",
        "author": "Stieg Larsson",
        "isbn": "9780307454546",
        "genre": "Mystery",
        "published_year": 2005,
        "summary": "A journalist and a hacker unravel a dark family mystery in Sweden.",
        "tags": "mystery,thriller,scandinavian",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780307454546-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "Gone Girl",
        "author": "Gillian Flynn",
        "isbn": "9780307588371",
        "genre": "Mystery",
        "published_year": 2012,
        "summary": "On their fifth wedding anniversary, Nick's wife Amy disappears.",
        "tags": "thriller,mystery,psychological",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780307588371-M.jpg",
        "total_copies": 1,
    },
    {
        "title": "Sapiens",
        "author": "Yuval Noah Harari",
        "isbn": "9780062316097",
        "genre": "Non-fiction",
        "published_year": 2011,
        "summary": "A sweeping history of humankind, from the Stone Age to the Silicon Age.",
        "tags": "history,anthropology,non-fiction",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062316097-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "Atomic Habits",
        "author": "James Clear",
        "isbn": "9780735211292",
        "genre": "Self-help",
        "published_year": 2018,
        "summary": "Tiny changes, remarkable results: a practical guide to building good habits.",
        "tags": "self-help,productivity,habits",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780735211292-M.jpg",
        "total_copies": 3,
    },
    {
        "title": "The Pragmatic Programmer",
        "author": "Andrew Hunt, David Thomas",
        "isbn": "9780135957059",
        "genre": "Technology",
        "published_year": 1999,
        "summary": "Timeless craftsmanship tips for software developers.",
        "tags": "programming,career,craft",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780135957059-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "isbn": "9780132350884",
        "genre": "Technology",
        "published_year": 2008,
        "summary": "Principles and patterns for writing readable, maintainable software.",
        "tags": "programming,best-practices",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780132350884-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "The Midnight Library",
        "author": "Matt Haig",
        "isbn": "9780525559474",
        "genre": "Fiction",
        "published_year": 2020,
        "summary": "A woman explores infinite alternate lives in a library between life and death.",
        "tags": "fiction,philosophical,feel-good",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780525559474-M.jpg",
        "total_copies": 2,
    },
    {
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "isbn": "9780593135204",
        "genre": "Science Fiction",
        "published_year": 2021,
        "summary": "A lone astronaut wakes up light-years from Earth with a planet-saving mission.",
        "tags": "sci-fi,space,first-contact",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780593135204-M.jpg",
        "total_copies": 2,
    },
]


def run() -> None:
    settings = get_settings()
    init_db()
    with Session(engine) as session:
        existing = session.exec(select(Book)).first()
        if existing is None:
            for data in DEMO_BOOKS:
                book = Book(**data, available_copies=data["total_copies"])
                session.add(book)
            session.commit()
            print(f"Seeded {len(DEMO_BOOKS)} books.")
        else:
            print("Books already present; skipping book seed.")

        for email in settings.admin_emails:
            user = session.exec(select(User).where(User.email == email)).first()
            if user is None:
                session.add(User(email=email, name=email.split("@")[0], role="admin"))
                print(f"Created admin user: {email}")
            elif user.role != "admin":
                user.role = "admin"
                session.add(user)
                print(f"Promoted existing user to admin: {email}")
        session.commit()


if __name__ == "__main__":
    run()
