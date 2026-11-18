import uuid
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import String, Text, func, inspect, or_, text
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from . import db
from .models import Category, Order, OrderItem, Payment, Product, Review, User, make_slug

admin = Blueprint("admin", __name__)
ORDER_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
ADMIN_TABLES = {
	"inventory": ("Inventory Management", ("inventory", "products"), "Current stock levels. Use Edit to update a product's stock."),
	"inventory_logs": ("Inventory Logs", ("inventory_logs",), "Inventory change history."),
	"sales": ("Sales Transactions", ("sales", "orders"), "Recorded sales transactions."),
	"sale_items": ("Sales Items", ("sale_items", "order_items"), "Items recorded for each sales transaction."),
	"payments": ("Payments", ("payments",), "Recorded payment transactions."),
	"suppliers": ("Suppliers", ("suppliers",), "Supplier records."),
	"loyalty": ("Loyalty Program", ("loyalty",), "Customer loyalty records."),
	"notifications": ("Notifications", ("notifications",), "System notifications."),
	"users": ("User Management", ("users",), "Registered customer and administrator accounts."),
	"customers": ("Customers", ("customers", "users"), "Registered customer accounts."),
	"reports": ("Reports", ("reports",), "Saved report records."),
}


def admin_required(view):
	@wraps(view)
	@login_required
	def wrapped(*args, **kwargs):
		if not current_user.is_admin:
			abort(403)
		return view(*args, **kwargs)
	return wrapped


def _image_signature_is_valid(extension, content):
	if extension in {"jpg", "jpeg"}:
		return content.startswith(b"\xff\xd8\xff")
	if extension == "png":
		return content.startswith(b"\x89PNG\r\n\x1a\n")
	if extension == "webp":
		return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
	return False


def _save_product_image(upload):
	if not upload or not upload.filename:
		return None
	safe_name = secure_filename(upload.filename)
	extension = Path(safe_name).suffix.lower().lstrip(".")
	if extension not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
		raise ValueError("Upload a JPG, PNG, or WebP image.")
	content = upload.stream.read()
	upload.stream.seek(0)
	if not _image_signature_is_valid(extension, content):
		raise ValueError("The uploaded file does not appear to be a valid image.")
	filename = f"{uuid.uuid4().hex}.{extension}"
	destination = Path(current_app.root_path).parent / "frontend" / "static" / "images" / "products" / "uploads" / filename
	destination.parent.mkdir(parents=True, exist_ok=True)
	upload.save(destination)
	return filename


def _product_form_data(form):
	name = form.get("name", "").strip()
	description = form.get("description", "").strip()
	category_id = form.get("category_id", type=int)
	try:
		price = Decimal(form.get("price", ""))
		stock = int(form.get("stock", ""))
	except (InvalidOperation, ValueError, TypeError):
		raise ValueError("Enter a valid price and whole-number stock quantity.")
	if not name or len(name) > 180 or not description:
		raise ValueError("Product name and description are required.")
	if price < 0 or price.as_tuple().exponent < -2 or price > Decimal("99999999.99"):
		raise ValueError("Enter a valid price with up to two decimal places.")
	if stock < 0 or stock > 2147483647:
		raise ValueError("Stock must be a non-negative whole number.")
	category = db.session.get(Category, category_id) if category_id else None
	if category is None:
		raise ValueError("Choose a valid category.")
	return name, description, price, stock, category, form.get("featured") == "on", form.get("active") == "on"


def _render_data_table(dataset):
	title, candidates, description = ADMIN_TABLES[dataset]
	inspector = inspect(db.engine)
	table_names = set(inspector.get_table_names())
	table_name = next((name for name in candidates if name in table_names), None)
	if table_name is None:
		return render_template(
			"admin/data_table.html",
			title=title,
			description=description,
			table_name=None,
			columns=[],
			rows=[],
			pagination=None,
			search="",
		)

	columns = inspector.get_columns(table_name)
	visible_columns = [
		column for column in columns
		if not any(secret in column["name"].lower() for secret in ("password", "secret", "token", "credential"))
	]
	search = request.args.get("q", "").strip()[:100]
	if not visible_columns:
		return render_template(
			"admin/data_table.html",
			title=title,
			description=description,
			table_name=table_name,
			columns=[],
			rows=[],
			pagination=None,
			search=search,
		)
	page = max(request.args.get("page", 1, type=int), 1)
	per_page = 20
	quote = db.engine.dialect.identifier_preparer.quote
	quoted_table = quote(table_name)
	where = []
	params = {}

	if dataset == "customers" and table_name == "users" and any(column["name"] == "role" for column in columns):
		where.append(f"{quote('role')} = :customer_role")
		params["customer_role"] = "customer"

	searchable_columns = [
		column for column in visible_columns
		if isinstance(column["type"], (String, Text))
	]
	if search and searchable_columns:
		where.append("(" + " OR ".join(
			f"LOWER({quote(column['name'])}) LIKE :search" for column in searchable_columns
		) + ")")
		params["search"] = f"%{search.lower()}%"

	where_sql = f" WHERE {' AND '.join(where)}" if where else ""
	count_sql = text(f"SELECT COUNT(*) FROM {quoted_table}{where_sql}")
	total = db.session.execute(count_sql, params).scalar_one()
	pages = max((total + per_page - 1) // per_page, 1)
	page = min(page, pages)
	select_columns = ", ".join(quote(column["name"]) for column in visible_columns)
	rows_sql = text(
		f"SELECT {select_columns} FROM {quoted_table}{where_sql} "
		f"ORDER BY {quote(columns[0]['name'])} DESC LIMIT :limit OFFSET :offset"
	)
	rows = db.session.execute(
		rows_sql,
		{**params, "limit": per_page, "offset": (page - 1) * per_page},
	).mappings().all()
	pagination = {
		"page": page,
		"pages": pages,
		"total": total,
		"has_prev": page > 1,
		"has_next": page < pages,
		"prev_num": page - 1,
		"next_num": page + 1,
	}
	return render_template(
		"admin/data_table.html",
		title=title,
		description=description,
		table_name=table_name,
		columns=visible_columns,
		rows=rows,
		pagination=pagination,
		search=search,
	)


@admin.route("/")
@admin_required
def dashboard():
	sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).join(Order.payment).filter(
		Payment.status == "paid",
		Order.status != "cancelled",
	).scalar()
	low_stock = Product.query.filter_by(active=True).filter(Product.stock <= 5).order_by(Product.stock.asc()).limit(8).all()
	recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
	today = datetime.now(timezone.utc).replace(tzinfo=None).date().replace(day=1)
	months = []
	for offset in range(5, -1, -1):
		month_index = today.month - 1 - offset
		year = today.year + month_index // 12
		month = month_index % 12 + 1
		months.append(datetime(year, month, 1))
	monthly_orders = Order.query.join(Order.payment).filter(
		Payment.status == "paid",
		Order.status != "cancelled",
		Order.created_at >= months[0],
	).all()
	monthly_sales = {month.strftime("%Y-%m"): Decimal("0.00") for month in months}
	for order in monthly_orders:
		key = order.created_at.strftime("%Y-%m")
		if key in monthly_sales:
			monthly_sales[key] += order.total
	recent_activities = [
		{"created_at": order.created_at, "description": f"Order {order.reference} was placed", "icon": "bi-receipt"}
		for order in recent_orders
	]
	recent_activities.extend(
		{"created_at": product.created_at, "description": f"Product {product.name} was added", "icon": "bi-box-seam"}
		for product in Product.query.order_by(Product.created_at.desc()).limit(5).all()
	)
	recent_activities.extend(
		{"created_at": category.created_at, "description": f"Category {category.name} was added", "icon": "bi-tags"}
		for category in Category.query.order_by(Category.created_at.desc()).limit(5).all()
	)
	recent_activities.sort(key=lambda activity: activity["created_at"], reverse=True)
	stock_totals = db.session.query(
		func.coalesce(func.sum(Product.stock), 0),
		func.count(Product.id),
	).filter(Product.active.is_(True)).one()
	return render_template(
		"admin/dashboard.html",
		product_count=Product.query.count(),
		category_count=Category.query.count(),
		customer_count=User.query.filter_by(role="customer").count(),
		order_count=Order.query.count(),
		sales=sales or Decimal("0.00"),
		low_stock=low_stock,
		low_stock_count=Product.query.filter_by(active=True).filter(Product.stock <= 5).count(),
		recent_orders=recent_orders,
		recent_activities=recent_activities[:6],
		monthly_sales=[
			{"label": month.strftime("%b"), "amount": monthly_sales[month.strftime("%Y-%m")]}
			for month in months
		],
		stock_units=stock_totals[0],
		inventory_product_count=stock_totals[1],
		out_of_stock_count=Product.query.filter_by(active=True, stock=0).count(),
	)


@admin.route("/products")
@admin_required
def products():
	search = request.args.get("q", "").strip()[:100]
	category_id = request.args.get("category", type=int)
	visibility = request.args.get("visibility", "")
	query = Product.query
	if search:
		query = query.filter(Product.name.ilike(f"%{search}%"))
	if category_id:
		query = query.filter_by(category_id=category_id)
	if visibility == "active":
		query = query.filter_by(active=True)
	elif visibility == "archived":
		query = query.filter_by(active=False)
	page = request.args.get("page", 1, type=int)
	pagination = query.order_by(Product.created_at.desc()).paginate(page=max(page, 1), per_page=20, error_out=False)
	return render_template(
		"admin/products.html",
		pagination=pagination,
		search=search,
		categories=Category.query.order_by(Category.name).all(),
		selected_category=category_id,
		visibility=visibility,
	)


@admin.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
	if request.method == "POST":
		try:
			name, description, price, stock, category, featured, active = _product_form_data(request.form)
			image_name = _save_product_image(request.files.get("image"))
			product = Product(
				name=name,
				slug=f"{make_slug(name)}-{uuid.uuid4().hex[:6]}",
				description=description,
				price=price,
				stock=stock,
				category=category,
				featured=featured,
				active=active,
				image_path=f"products/uploads/{image_name}" if image_name else "products/placeholder.svg",
			)
			db.session.add(product)
			db.session.commit()
			flash("Product created.", "success")
			return redirect(url_for("admin.products"))
		except ValueError as error:
			flash(str(error), "error")
		except IntegrityError:
			db.session.rollback()
			flash("A product with conflicting details could not be saved.", "error")
	return render_template("admin/product_form.html", product=None, categories=Category.query.order_by(Category.name).all())


@admin.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
	product = db.session.get(Product, product_id) or abort(404)
	if request.method == "POST":
		try:
			name, description, price, stock, category, featured, active = _product_form_data(request.form)
			image_name = _save_product_image(request.files.get("image"))
			product.name = name
			product.slug = f"{make_slug(name)}-{product.id}"
			product.description = description
			product.price = price
			product.stock = stock
			product.category = category
			product.featured = featured
			product.active = active
			if image_name:
				product.image_path = f"products/uploads/{image_name}"
			db.session.commit()
			flash("Product updated.", "success")
			return redirect(url_for("admin.products"))
		except ValueError as error:
			flash(str(error), "error")
		except IntegrityError:
			db.session.rollback()
			flash("A product with conflicting details could not be saved.", "error")
	return render_template("admin/product_form.html", product=product, categories=Category.query.order_by(Category.name).all())


@admin.post("/products/<int:product_id>/delete")
@admin_required
def product_delete(product_id):
	product = db.session.get(Product, product_id) or abort(404)
	if product.order_items:
		product.active = False
		flash("This product appears in order history, so it was archived instead of deleted.", "info")
	else:
		db.session.delete(product)
		flash("Product deleted.", "success")
	db.session.commit()
	return redirect(url_for("admin.products"))


@admin.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
	if request.method == "POST":
		name = request.form.get("name", "").strip()
		description = request.form.get("description", "").strip()
		if not name or len(name) > 100:
			flash("Enter a category name (up to 100 characters).", "error")
		elif Category.query.filter(func.lower(Category.name) == name.lower()).first():
			flash("That category already exists.", "error")
		else:
			db.session.add(Category(name=name, slug=f"{make_slug(name)}-{uuid.uuid4().hex[:5]}", description=description[:500]))
			db.session.commit()
			flash("Category added.", "success")
		return redirect(url_for("admin.categories"))
	search = request.args.get("q", "").strip()[:100]
	query = Category.query
	if search:
		query = query.filter(Category.name.ilike(f"%{search}%"))
	return render_template("admin/categories.html", categories=query.order_by(Category.name).all(), search=search)


@admin.post("/categories/<int:category_id>/delete")
@admin_required
def category_delete(category_id):
	category = db.session.get(Category, category_id) or abort(404)
	if category.products:
		flash("Move or remove this category's products before deleting it.", "error")
	else:
		db.session.delete(category)
		db.session.commit()
		flash("Category deleted.", "success")
	return redirect(url_for("admin.categories"))


@admin.route("/orders")
@admin_required
def orders():
	status = request.args.get("status", "")
	query = Order.query
	if status in ORDER_STATUSES:
		query = query.filter_by(status=status)
	search = request.args.get("q", "").strip()[:100]
	if search:
		term = f"%{search}%"
		query = query.filter(
			or_(
				Order.reference.ilike(term),
				Order.customer_name.ilike(term),
				Order.phone.ilike(term),
			)
		)
	page = request.args.get("page", 1, type=int)
	pagination = query.order_by(Order.created_at.desc()).paginate(page=max(page, 1), per_page=25, error_out=False)
	return render_template(
		"admin/orders.html",
		pagination=pagination,
		selected_status=status,
		statuses=sorted(ORDER_STATUSES),
		search=search,
	)


@admin.post("/orders/<int:order_id>/status")
@admin_required
def order_status(order_id):
	order = db.session.get(Order, order_id) or abort(404)
	new_status = request.form.get("status", "")
	if new_status not in ORDER_STATUSES:
		flash("Choose a valid order status.", "error")
		return redirect(url_for("admin.orders"))
	if order.status == "cancelled" and new_status != "cancelled":
		flash("Cancelled orders cannot be reopened; contact the customer to arrange a new order.", "error")
		return redirect(url_for("admin.orders"))
	if new_status == "cancelled" and order.status != "cancelled":
		if order.status == "delivered":
			flash("Delivered orders cannot be cancelled here.", "error")
			return redirect(url_for("admin.orders"))
		for item in order.items:
			item.product.stock += item.quantity
	order.status = new_status
	db.session.commit()
	flash("Order status updated.", "success")
	return redirect(url_for("admin.orders"))


@admin.post("/orders/<int:order_id>/payment")
@admin_required
def order_payment_status(order_id):
	order = db.session.get(Order, order_id) or abort(404)
	if order.payment is None:
		abort(404)
	if order.payment.method != "cod" or order.status != "delivered":
		flash("COD collection can only be recorded for a delivered order.", "error")
	elif order.payment.status != "paid":
		order.payment.status = "paid"
		db.session.commit()
		flash("COD collection recorded as verified.", "success")
	else:
		flash("This order is already marked as collected.", "info")
	return redirect(url_for("admin.orders"))


@admin.route("/customers")
@admin_required
def customers():
	if "customers" in inspect(db.engine).get_table_names():
		return redirect(url_for("admin.data_table", dataset="customers"))
	search = request.args.get("q", "").strip()[:100]
	query = User.query.filter_by(role="customer")
	if search:
		term = f"%{search}%"
		query = query.filter(or_(User.name.ilike(term), User.email.ilike(term), User.phone.ilike(term)))
	page = request.args.get("page", 1, type=int)
	pagination = query.order_by(User.created_at.desc()).paginate(page=max(page, 1), per_page=25, error_out=False)
	return render_template("admin/customers.html", pagination=pagination, search=search)


@admin.route("/inventory")
@admin_required
def inventory():
	search = request.args.get("q", "").strip()[:100]
	stock_filter = request.args.get("stock", "")
	query = Product.query.filter_by(active=True)
	if search:
		query = query.filter(Product.name.ilike(f"%{search}%"))
	if stock_filter == "low":
		query = query.filter(Product.stock.between(1, 5))
	elif stock_filter == "out":
		query = query.filter_by(stock=0)
	page = max(request.args.get("page", 1, type=int), 1)
	pagination = query.order_by(Product.stock.asc(), Product.name.asc()).paginate(
		page=page, per_page=25, error_out=False
	)
	return render_template("admin/inventory.html", pagination=pagination, search=search, stock_filter=stock_filter)


@admin.route("/sales")
@admin_required
def sales():
	if "sales" not in inspect(db.engine).get_table_names():
		return redirect(url_for("admin.orders"))
	return _render_data_table("sales")


@admin.route("/data/<dataset>")
@admin_required
def data_table(dataset):
	if dataset not in ADMIN_TABLES:
		abort(404)
	return _render_data_table(dataset)


@admin.route("/settings")
@admin_required
def settings():
	return render_template("admin/settings.html")


@admin.route("/reviews")
@admin_required
def reviews():
	pending_reviews = Review.query.filter_by(approved=False).order_by(Review.created_at.asc()).all()
	return render_template("admin/reviews.html", reviews=pending_reviews)


@admin.post("/reviews/<int:review_id>")
@admin_required
def review_moderate(review_id):
	review = db.session.get(Review, review_id) or abort(404)
	action = request.form.get("action")
	if action == "approve":
		review.approved = True
		db.session.commit()
		flash("Review approved and published.", "success")
	elif action == "reject":
		db.session.delete(review)
		db.session.commit()
		flash("Review rejected and removed.", "info")
	else:
		flash("Choose approve or reject.", "error")
	return redirect(url_for("admin.reviews"))


@admin.route("/reports")
@admin_required
def reports():
	if "reports" in inspect(db.engine).get_table_names():
		return redirect(url_for("admin.data_table", dataset="reports"))
	start_text = request.args.get("start", "").strip()
	end_text = request.args.get("end", "").strip()
	query = Order.query.join(Order.payment).filter(Payment.status == "paid", Order.status != "cancelled")
	try:
		if start_text:
			query = query.filter(Order.created_at >= datetime.combine(datetime.strptime(start_text, "%Y-%m-%d").date(), time.min))
		if end_text:
			query = query.filter(Order.created_at <= datetime.combine(datetime.strptime(end_text, "%Y-%m-%d").date(), time.max))
	except ValueError:
		flash("Use valid dates in YYYY-MM-DD format.", "error")
		return redirect(url_for("admin.reports"))
	selected_orders = query.order_by(Order.created_at.desc()).all()
	total_sales = sum((order.total for order in selected_orders), Decimal("0.00"))
	return render_template("admin/reports.html", orders=selected_orders, total_sales=total_sales, start=start_text, end=end_text)
