import re
from decimal import Decimal

from sqlalchemy import inspect, text

from backend import db
from backend.models import Order, Payment
from tests.conftest import create_product, create_user, login


def admin_login(client, app):
    with app.app_context():
        create_user(email="admin@example.com", role="admin")
    return login(client, email="admin@example.com")


def test_admin_dashboard_and_sidebar_pages_render(client, app):
    admin_login(client, app)
    paths = (
        "/admin/",
        "/admin/products",
        "/admin/categories",
        "/admin/inventory",
        "/admin/sales",
        "/admin/data/inventory_logs",
        "/admin/data/suppliers",
        "/admin/data/sales",
        "/admin/data/sale_items",
        "/admin/data/payments",
        "/admin/reports",
        "/admin/customers",
        "/admin/data/loyalty",
        "/admin/data/notifications",
        "/admin/data/users",
        "/admin/settings",
    )
    for path in paths:
        response = client.get(path, follow_redirects=True)
        assert response.status_code == 200, path
    dashboard = client.get("/admin/")
    assert b"Sales overview" in dashboard.data
    assert b"Inventory summary" in dashboard.data
    assert b"ADMIN CONSOLE" in dashboard.data


def test_optional_admin_tables_are_read_only_searchable_and_never_created(client, app):
    admin_login(client, app)
    unavailable = client.get("/admin/data/inventory_logs")
    assert b"Table not available" in unavailable.data

    with app.app_context():
        db.session.execute(text(
            "CREATE TABLE suppliers (id INTEGER PRIMARY KEY, supplier_name VARCHAR(100) NOT NULL)"
        ))
        db.session.execute(text(
            "INSERT INTO suppliers (supplier_name) VALUES ('North Supply'), ('South Supply')"
        ))
        db.session.commit()

    results = client.get("/admin/data/suppliers?q=North")
    assert results.status_code == 200
    assert b"North Supply" in results.data
    assert b"South Supply" not in results.data
    users = client.get("/admin/data/users")
    assert users.status_code == 200
    assert b"password_hash" not in users.data
    with app.app_context():
        assert "inventory_logs" not in inspect(db.engine).get_table_names()


def test_dashboard_uses_database_totals_and_excludes_cancelled_revenue(client, app):
    admin_login(client, app)
    with app.app_context():
        customer = create_user(email="buyer@example.com")
        create_product(name="Live Stock Phone", stock=2)
        db.session.add_all([
            Order(
                reference="MG-PAID-001",
                user_id=customer.id,
                customer_name=customer.name,
                phone=customer.phone,
                shipping_address="1 Store Street",
                total=Decimal("1234.50"),
                status="delivered",
                payment_method="cod",
                payment=Payment(method="cod", status="paid"),
            ),
            Order(
                reference="MG-CANCEL-01",
                user_id=customer.id,
                customer_name=customer.name,
                phone=customer.phone,
                shipping_address="1 Store Street",
                total=Decimal("9999.00"),
                status="cancelled",
                payment_method="cod",
                payment=Payment(method="cod", status="paid"),
            ),
        ])
        db.session.commit()

    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"1,234.50" in response.data
    assert b"Live Stock Phone" in response.data
    assert b"MG-PAID-001" in response.data
    revenue_card = re.search(rb'<article class="stat-card stat-highlight">(.*?)</article>', response.data, re.S)
    assert revenue_card is not None
    assert b"1,234.50" in revenue_card.group(1)
    assert b"9,999.00" not in revenue_card.group(1)


def test_non_admin_cannot_access_new_admin_pages(client):
    assert client.get("/admin/inventory").status_code == 302
    assert client.get("/admin/data/suppliers").status_code == 302
