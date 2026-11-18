import pytest

from backend import create_app, db
from backend.models import Category, Product, User


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def create_user(email="customer@example.com", password="password123", role="customer"):
    user = User(name="Test Customer", email=email, phone="09171234567", role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def create_product(name="Test Gadget", price="1200.00", stock=5):
    category = Category.query.filter_by(slug="test-category").first()
    if category is None:
        category = Category(name="Test Category", slug="test-category", description="Test products")
        db.session.add(category)
        db.session.flush()
    product = Product(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{Product.query.count() + 1}",
        description="A locally tested gadget.",
        price=price,
        stock=stock,
        category=category,
        image_path="products/phone.svg",
        active=True,
    )
    db.session.add(product)
    db.session.commit()
    return product


def login(client, email="customer@example.com", password="password123"):
    return client.post("/login", data={"email": email, "password": password})