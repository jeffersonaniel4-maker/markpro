import re
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def make_slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer", index=True)
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=False, default="")
    products = db.relationship("Product", back_populates="category")


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
        db.CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_path = db.Column(db.String(255), nullable=False, default="products/placeholder.svg")
    featured = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    category = db.relationship("Category", back_populates="products")
    order_items = db.relationship("OrderItem", back_populates="product")
    reviews = db.relationship("Review", back_populates="product", cascade="all, delete-orphan")

    @property
    def average_rating(self):
        approved = [review.rating for review in self.reviews if review.approved]
        return sum(approved) / len(approved) if approved else 0


class CartItem(TimestampMixin, db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
        db.CheckConstraint("quantity >= 1", name="ck_cart_items_quantity_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    user = db.relationship("User", back_populates="cart_items")
    product = db.relationship("Product")


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint("total >= 0", name="ck_orders_total_nonnegative"),
        db.Index("ix_orders_created_status", "created_at", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    shipping_address = db.Column(db.String(500), nullable=False)
    notes = db.Column(db.String(1000), nullable=False, default="")
    total = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    payment_method = db.Column(db.String(30), nullable=False, default="cod")
    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = db.relationship("Payment", back_populates="order", uselist=False, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    __table_args__ = (db.CheckConstraint("quantity >= 1", name="ck_order_items_quantity_positive"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    product_name = db.Column(db.String(180), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    method = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending")
    provider_reference = db.Column(db.String(120), nullable=True)
    order = db.relationship("Order", back_populates="payment")


class Review(TimestampMixin, db.Model):
    __tablename__ = "reviews"
    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        db.UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.String(1500), nullable=False)
    approved = db.Column(db.Boolean, nullable=False, default=False)
    user = db.relationship("User", back_populates="reviews")
    product = db.relationship("Product", back_populates="reviews")