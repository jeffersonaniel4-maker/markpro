from backend import db
from backend.models import Order, OrderItem, Payment, Product, Review
from tests.conftest import create_product, create_user, login


def test_product_browsing_search_and_detail(client, app):
    with app.app_context():
        product = create_product(name="Blue Phone")
        slug = product.slug
    response = client.get("/products?q=Blue")
    assert response.status_code == 200
    assert b"Blue Phone" in response.data
    detail = client.get(f"/products/{slug}")
    assert detail.status_code == 200
    assert b"1,200.00" in detail.data


def test_invalid_product_slug_returns_404(client):
    assert client.get("/products/not-a-real-product").status_code == 404


def test_public_pages_render(client):
    for path in ("/", "/categories", "/about", "/contact", "/login", "/register", "/products"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_purchase_review_waits_for_admin_approval(client, app):
    with app.app_context():
        customer = create_user()
        create_user(email="admin@example.com", role="admin")
        product = create_product(name="Reviewed Phone")
        slug = product.slug
        order = Order(
            reference="MG-REVIEW123",
            user_id=customer.id,
            customer_name=customer.name,
            phone=customer.phone,
            shipping_address="123 Sample Street",
            total=product.price,
            payment_method="cod",
            items=[OrderItem(product_id=product.id, product_name=product.name, unit_price=product.price, quantity=1)],
            payment=Payment(method="cod"),
        )
        db.session.add(order)
        db.session.commit()
    login(client)
    assert client.post(f"/products/{slug}/reviews", data={"rating": "5", "body": "Works exactly as expected."}).status_code == 403
    with app.app_context():
        order = Order.query.filter_by(reference="MG-REVIEW123").one()
        order.status = "delivered"
        order.payment.status = "paid"
        db.session.commit()
    response = client.post(f"/products/{slug}/reviews", data={"rating": "5", "body": "Works exactly as expected."})
    assert response.status_code == 302
    with app.app_context():
        review = Review.query.one()
        review_id = review.id
        assert review.approved is False
    assert b"Works exactly as expected." not in client.get(f"/products/{slug}").data
    client.post("/logout")
    admin_client = app.test_client()
    login_response = admin_client.post("/login", data={"email": "admin@example.com", "password": "password123"})
    assert login_response.status_code == 302
    moderation_response = admin_client.post(f"/admin/reviews/{review_id}", data={"action": "approve"})
    assert moderation_response.status_code == 302
    assert b"Works exactly as expected." in client.get(f"/products/{slug}").data


def test_seed_demo_adds_iphone_lineup_without_duplicates(app, client):
    runner = app.test_cli_runner()
    first_run = runner.invoke(args=["seed-demo"])
    assert first_run.exit_code == 0
    with app.app_context():
        assert Product.query.filter(Product.slug.like("apple-iphone-%")).count() == 8
    second_run = runner.invoke(args=["seed-demo"])
    assert second_run.exit_code == 0
    assert "added 0 missing demo products" in second_run.output
    response = client.get("/products?q=iPhone")
    for model in ("Apple iPhone 15", "Apple iPhone 16", "Apple iPhone 17", "Apple iPhone 18"):
        assert model.encode() in response.data