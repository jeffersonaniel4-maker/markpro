import secrets
from decimal import Decimal
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .models import CartItem, Category, Order, OrderItem, Payment, Product, Review, User

main = Blueprint("main", __name__)


def _safe_next_url(target):
    if not target:
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _cart():
    return CartItem.query.filter_by(user_id=current_user.id).join(Product).all()


def _get_owned_order(reference):
    order = Order.query.filter_by(reference=reference, user_id=current_user.id).first()
    if order is None:
        abort(404)
    return order


@main.route("/")
def index():
    featured = Product.query.filter_by(active=True, featured=True).order_by(Product.created_at.desc()).limit(4).all()
    new_arrivals = Product.query.filter_by(active=True).order_by(Product.created_at.desc()).limit(4).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template("index.html", featured=featured, new_arrivals=new_arrivals, categories=categories)


@main.route("/products")
def products():
    query = Product.query.filter_by(active=True)
    search = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest")
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if category:
        query = query.join(Category).filter(Category.slug == category)
    ordering = {
        "price-low": Product.price.asc(),
        "price-high": Product.price.desc(),
        "name": Product.name.asc(),
        "newest": Product.created_at.desc(),
    }.get(sort, Product.created_at.desc())
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(ordering).paginate(page=max(page, 1), per_page=12, error_out=False)
    return render_template(
        "products.html",
        pagination=pagination,
        categories=Category.query.order_by(Category.name).all(),
        search=search,
        selected_category=category,
        sort=sort,
    )


@main.route("/products/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, active=True).first_or_404()
    reviews = Review.query.filter_by(product_id=product.id, approved=True).order_by(Review.created_at.desc()).all()
    has_purchased = False
    already_reviewed = False
    if current_user.is_authenticated:
        has_purchased = db.session.query(OrderItem.id).join(Order).join(Payment).filter(
            Order.user_id == current_user.id,
            OrderItem.product_id == product.id,
            Order.status == "delivered",
            Payment.status == "paid",
        ).first() is not None
        already_reviewed = Review.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
    return render_template(
        "product_detail.html",
        product=product,
        reviews=reviews,
        has_purchased=has_purchased,
        already_reviewed=already_reviewed,
    )


@main.route("/categories")
def categories():
    return render_template("categories.html", categories=Category.query.order_by(Category.name).all())


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        errors = []
        if not name or len(name) > 120:
            errors.append("Enter your name (up to 120 characters).")
        if "@" not in email or len(email) > 255:
            errors.append("Enter a valid email address.")
        if not phone or len(phone) > 30:
            errors.append("Enter a valid phone number.")
        if len(password) < 8:
            errors.append("Your password must be at least 8 characters.")
        if password != confirmation:
            errors.append("The password confirmation does not match.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("register.html", form=request.form), 400
        user = User(name=name, email=email, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your account is ready. Welcome to MARKS GADGETS.", "success")
        return redirect(url_for("main.profile"))
    return render_template("register.html", form={})


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Email or password is incorrect.", "error")
            return render_template("login.html", form=request.form), 401
        login_user(user, remember=request.form.get("remember") == "on")
        flash("You are now signed in.", "success")
        return redirect(_safe_next_url(request.args.get("next")) or url_for("main.profile"))
    return render_template("login.html", form={})


@main.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@main.post("/cart/add/<int:product_id>")
@login_required
def cart_add(product_id):
    product = Product.query.filter_by(id=product_id, active=True).first_or_404()
    try:
        quantity = int(request.form.get("quantity", "1"))
    except (TypeError, ValueError):
        quantity = 0
    if quantity < 1 or quantity > 99:
        flash("Choose a quantity between 1 and 99.", "error")
        return redirect(request.referrer or url_for("main.products"))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    updated_quantity = quantity + (item.quantity if item else 0)
    if product.stock < updated_quantity:
        flash(f"Only {product.stock} units are currently available.", "error")
        return redirect(request.referrer or url_for("main.product_detail", slug=product.slug))
    if item:
        item.quantity = updated_quantity
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product.id, quantity=quantity))
    db.session.commit()
    flash(f"{product.name} added to your cart.", "success")
    return redirect(url_for("main.cart"))


@main.route("/cart")
@login_required
def cart():
    items = _cart()
    total = sum((item.product.price * item.quantity for item in items), Decimal("0.00"))
    return render_template("cart.html", items=items, total=total)


@main.post("/cart/update/<int:item_id>")
@login_required
def cart_update(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    try:
        quantity = int(request.form.get("quantity", "0"))
    except (TypeError, ValueError):
        quantity = 0
    if quantity < 1 or quantity > item.product.stock or quantity > 99:
        flash("Choose a quantity within the available stock.", "error")
    else:
        item.quantity = quantity
        db.session.commit()
        flash("Cart updated.", "success")
    return redirect(url_for("main.cart"))


@main.post("/cart/remove/<int:item_id>")
@login_required
def cart_remove(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from your cart.", "info")
    return redirect(url_for("main.cart"))


@main.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = _cart()
    if not items:
        flash("Your cart is empty.", "info")
        return redirect(url_for("main.products"))
    total = sum((item.product.price * item.quantity for item in items), Decimal("0.00"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_method = request.form.get("payment_method", "cod")
        errors = []
        if not name or len(name) > 120:
            errors.append("Enter the recipient's name.")
        if not phone or len(phone) > 30:
            errors.append("Enter a valid contact number.")
        if not address or len(address) > 500:
            errors.append("Enter a shipping address (up to 500 characters).")
        if len(notes) > 1000:
            errors.append("Order notes must be 1,000 characters or fewer.")
        if payment_method != "cod":
            errors.append("Only Cash on Delivery is available right now. Online payments are not integrated.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("checkout.html", items=items, total=total, form=request.form), 400

        try:
            locked_products = {}
            for item in items:
                product = db.session.execute(
                    select(Product)
                    .where(Product.id == item.product_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).scalar_one_or_none()
                if product is None or not product.active or product.stock < item.quantity:
                    raise ValueError(f"{item.product.name} no longer has enough stock. Please review your cart.")
                locked_products[item.product_id] = product

            verified_total = Decimal("0.00")
            order_items = []
            for item in items:
                product = locked_products[item.product_id]
                verified_total += product.price * item.quantity
                order_items.append(OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=item.quantity,
                ))
            order = Order(
                reference=f"MG-{secrets.token_hex(5).upper()}",
                user_id=current_user.id,
                customer_name=name,
                phone=phone,
                shipping_address=address,
                notes=notes,
                total=verified_total,
                status="pending",
                payment_method="cod",
                items=order_items,
                payment=Payment(method="cod", status="pending"),
            )
            db.session.add(order)
            for item in items:
                locked_products[item.product_id].stock -= item.quantity
                db.session.delete(item)
            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
            return redirect(url_for("main.cart"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("We could not place the order. Your cart and stock were not changed; please try again.", "error")
            return redirect(url_for("main.checkout"))
        return redirect(url_for("main.order_confirmation", reference=order.reference))
    return render_template("checkout.html", items=items, total=total, form={})


@main.route("/orders/<reference>/confirmation")
@login_required
def order_confirmation(reference):
    return render_template("order_confirmation.html", order=_get_owned_order(reference))


@main.route("/account", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            if not name or len(name) > 120 or not phone or len(phone) > 30:
                flash("Enter a valid name and phone number.", "error")
            else:
                current_user.name = name
                current_user.phone = phone
                db.session.commit()
                flash("Profile updated.", "success")
        elif action == "password":
            old_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            if not current_user.check_password(old_password):
                flash("Your current password is incorrect.", "error")
            elif len(new_password) < 8:
                flash("Your new password must be at least 8 characters.", "error")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password changed successfully.", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html")


@main.route("/orders")
@login_required
def order_history():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("order_history.html", orders=orders)


@main.route("/orders/<reference>")
@login_required
def order_detail(reference):
    return render_template("order_detail.html", order=_get_owned_order(reference))


@main.post("/products/<slug>/reviews")
@login_required
def add_review(slug):
    product = Product.query.filter_by(slug=slug, active=True).first_or_404()
    purchased = db.session.query(OrderItem.id).join(Order).join(Payment).filter(
        Order.user_id == current_user.id,
        OrderItem.product_id == product.id,
        Order.status == "delivered",
        Payment.status == "paid",
    ).first()
    if not purchased:
        abort(403)
    if Review.query.filter_by(user_id=current_user.id, product_id=product.id).first():
        flash("You have already submitted a review for this product.", "info")
        return redirect(url_for("main.product_detail", slug=slug))
    try:
        rating = int(request.form.get("rating", "0"))
    except (ValueError, TypeError):
        rating = 0
    body = request.form.get("body", "").strip()
    if rating not in range(1, 6) or not body or len(body) > 1500:
        flash("Choose a rating from 1 to 5 and write a review (up to 1,500 characters).", "error")
        return redirect(url_for("main.product_detail", slug=slug))
    db.session.add(Review(user_id=current_user.id, product_id=product.id, rating=rating, body=body))
    db.session.commit()
    flash("Thanks. Your review will appear after it is approved.", "success")
    return redirect(url_for("main.product_detail", slug=slug))


@main.route("/about")
def about():
    return render_template("about.html")


@main.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if not name or "@" not in email or not message or len(message) > 3000:
            flash("Please provide a name, valid email, and message under 3,000 characters.", "error")
        else:
            flash("Email sending is not configured yet. Please contact us directly at support@marksgadgets.ph.", "info")
        return redirect(url_for("main.contact"))
    return render_template("contact.html")