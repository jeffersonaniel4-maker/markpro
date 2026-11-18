from tests.conftest import create_product, create_user, login
from backend import db
from backend.models import CartItem


def test_cart_add_update_and_remove(client, app):
    with app.app_context():
        create_user()
        product = create_product(stock=4)
        product_id = product.id
    login(client)
    assert client.post(f"/cart/add/{product_id}", data={"quantity": "2"}).status_code == 302
    with app.app_context():
        item = CartItem.query.one()
        item_id = item.id
    client.post(f"/cart/update/{item_id}", data={"quantity": "3"})
    with app.app_context():
        assert CartItem.query.one().quantity == 3
    client.post(f"/cart/remove/{item_id}")
    with app.app_context():
        assert CartItem.query.count() == 0


def test_cart_rejects_bad_product_and_quantity(client, app):
    with app.app_context():
        create_user()
        product = create_product(stock=2)
        product_id = product.id
    login(client)
    assert client.post("/cart/add/99999", data={"quantity": "1"}).status_code == 404
    client.post(f"/cart/add/{product_id}", data={"quantity": "3"})
    with app.app_context():
        assert CartItem.query.count() == 0