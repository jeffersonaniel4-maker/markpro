from backend import db
from backend.models import CartItem, Order, OrderItem, Payment, Product
from tests.conftest import create_product, create_user, login


def _checkout_data(**overrides):
    data = {
        "name": "Test Customer",
        "phone": "09171234567",
        "address": "123 Sample Street, Quezon City",
        "notes": "Leave at the front desk",
        "payment_method": "cod",
        "total": "0.01",
    }
    data.update(overrides)
    return data


def test_checkout_uses_server_price_and_updates_stock_atomically(client, app):
    with app.app_context():
        create_user()
        product = create_product(price="100.00", stock=3)
        product_id = product.id
    login(client)
    client.post(f"/cart/add/{product_id}", data={"quantity": "3"})
    response = client.post("/checkout", data=_checkout_data())
    assert response.status_code == 302
    with app.app_context():
        order = Order.query.one()
        assert str(order.total) == "300.00"
        assert db.session.get(Product, product_id).stock == 0
        assert CartItem.query.count() == 0
        assert order.payment.status == "pending"


def test_checkout_rejects_stock_that_changed_after_cart_add(client, app):
    with app.app_context():
        create_user()
        product = create_product(price="75.00", stock=4)
        product_id = product.id
    login(client)
    client.post(f"/cart/add/{product_id}", data={"quantity": "3"})
    with app.app_context():
        db.session.get(Product, product_id).stock = 1
        db.session.commit()
    response = client.post("/checkout", data=_checkout_data())
    assert response.status_code == 302
    with app.app_context():
        assert Order.query.count() == 0
        assert db.session.get(Product, product_id).stock == 1
        assert CartItem.query.one().quantity == 3


def test_checkout_requires_customer_and_admin_access_is_restricted(client, app):
    assert client.get("/checkout").status_code == 302
    assert client.get("/admin/").status_code == 302
    with app.app_context():
        create_user()
    login(client)
    assert client.get("/admin/").status_code == 403


def test_admin_pages_render_for_administrator(client, app):
    with app.app_context():
        create_user(email="admin@example.com", role="admin")
    login(client, email="admin@example.com")
    for path in (
        "/admin/",
        "/admin/products",
        "/admin/products/new",
        "/admin/categories",
        "/admin/orders",
        "/admin/customers",
        "/admin/reviews",
        "/admin/reports",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_customer_cannot_view_another_customers_order(client, app):
    with app.app_context():
        owner = create_user(email="owner@example.com")
        create_user(email="other@example.com")
        product = create_product()
        order = Order(
            reference="MG-OWNER1234",
            user_id=owner.id,
            customer_name=owner.name,
            phone=owner.phone,
            shipping_address="123 Sample Street",
            total=product.price,
            payment_method="cod",
            items=[OrderItem(product_id=product.id, product_name=product.name, unit_price=product.price, quantity=1)],
            payment=Payment(method="cod"),
        )
        db.session.add(order)
        db.session.commit()
    login(client, email="other@example.com")
    assert client.get("/orders/MG-OWNER1234").status_code == 404