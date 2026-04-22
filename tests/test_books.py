def test_create_requires_admin(client, member_client):
    # member shouldn't be able to create
    r = member_client.post(
        "/books/new",
        data={"title": "X", "author": "Y", "total_copies": 1},
        follow_redirects=False,
    )
    assert r.status_code in (401, 403)


def test_admin_crud_and_search(admin_client):
    r = admin_client.post(
        "/books/new",
        data={
            "title": "Unique Test Tome",
            "author": "Test Author",
            "genre": "Fantasy",
            "tags": "magic,quest",
            "total_copies": 2,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    # Search finds it
    r = admin_client.get("/books?q=unique+test")
    assert r.status_code == 200
    assert "Unique Test Tome" in r.text

    # Filter by genre
    r = admin_client.get("/books?genre=Fantasy")
    assert "Unique Test Tome" in r.text
