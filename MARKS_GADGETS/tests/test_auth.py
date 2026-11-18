from backend import db
from backend.models import User


def test_registration_hashes_password_and_logs_in(client, app):
    response = client.post("/register", data={
        "name": "Mika Santos",
        "email": "mika@example.com",
        "phone": "09171234567",
        "password": "strong-pass-123",
        "confirm_password": "strong-pass-123",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="mika@example.com").one()
        assert user.password_hash != "strong-pass-123"
        assert user.check_password("strong-pass-123")


def test_duplicate_registration_is_rejected(client, app):
    client.post("/register", data={
        "name": "Mika Santos", "email": "mika@example.com", "phone": "09171234567",
        "password": "strong-pass-123", "confirm_password": "strong-pass-123",
    })
    client.post("/logout")
    response = client.post("/register", data={
        "name": "Another Name", "email": "mika@example.com", "phone": "09170000000",
        "password": "strong-pass-123", "confirm_password": "strong-pass-123",
    })
    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="mika@example.com").count() == 1


def test_invalid_login_credentials_are_rejected(client, app):
    with app.app_context():
        user = User(name="Test", email="test@example.com", phone="09171234567")
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()
    response = client.post("/login", data={"email": "test@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert b"incorrect" in response.data.lower()