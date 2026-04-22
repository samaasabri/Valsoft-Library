def _create_book(admin_client, title="Loanable Book", copies=1):
    admin_client.post(
        "/books/new",
        data={"title": title, "author": "Auth", "total_copies": copies},
        follow_redirects=False,
    )


def test_checkout_and_return_flow(admin_client, member_client):
    _create_book(admin_client, title="Loanable Book", copies=1)

    # Grab the book id by listing
    listing = admin_client.get("/books?q=Loanable")
    assert "Loanable Book" in listing.text

    # Naive extraction: find first book-<id> in the page
    import re
    m = re.search(r'id="book-(\d+)"', listing.text)
    assert m, "book id not found on page"
    book_id = int(m.group(1))

    # Member borrows
    r = member_client.post(f"/books/{book_id}/checkout", follow_redirects=False)
    assert r.status_code in (200, 303)

    # Member now has an active loan on My Loans
    r = member_client.get("/my-loans")
    assert "Loanable Book" in r.text

    # Second checkout should fail (no copies left)
    r2 = member_client.post(f"/books/{book_id}/checkout", follow_redirects=False)
    assert r2.status_code in (400, 500)


def test_ai_endpoints_degrade_without_key(member_client):
    r = member_client.post(
        "/ai/autofill",
        json={"title": "1984", "author": "George Orwell"},
    )
    # 503 when GEMINI_API_KEY is not configured
    assert r.status_code == 503
