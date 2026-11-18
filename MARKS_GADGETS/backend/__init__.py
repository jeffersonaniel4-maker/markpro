import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import click
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy

from .config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config=None):
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(project_root / "frontend" / "templates"),
        static_folder=str(project_root / "frontend" / "static"),
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(project_root / "instance", exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "info"

    from . import models
    from .routes import main
    from .admin import admin

    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix="/admin")

    @app.template_filter("peso")
    def peso(amount):
        return f"₱{amount:,.2f}"

    @app.context_processor
    def inject_template_helpers():
        return {"current_year": datetime.now().year}

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @app.cli.command("init-db")
    def init_db_command():
        """Create all application tables."""
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Add missing starter categories and products without duplicating listings."""
        category_data = [
            ("Smartphones", "smartphones", "Phones for work, play, and everything between."),
            ("Laptops", "laptops", "Portable computers for study and work."),
            ("Tablets", "tablets", "Versatile screens for creativity and entertainment."),
            ("Accessories", "accessories", "Everyday essentials for your devices."),
            ("Audio", "audio", "Headphones, speakers, and more."),
        ]
        categories = []
        for name, slug, description in category_data:
            category = models.Category.query.filter_by(slug=slug).first()
            if category is None:
                category = models.Category(name=name, slug=slug, description=description)
                db.session.add(category)
            categories.append(category)
        db.session.flush()
        product_data = [
            ("Nova X5 Smartphone", "A responsive 5G smartphone with a vivid OLED display.", "smartphones", "18999.00", 18, "phones"),
            ("Orbit Pro 14 Laptop", "A lightweight laptop built for multitasking and study.", "laptops", "42999.00", 8, "laptops"),
            ("Tab Air 11", "An 11-inch tablet for reading, streaming, and sketching.", "tablets", "16999.00", 12, "tablets"),
            ("Pulse Wireless Earbuds", "Compact wireless earbuds with a charging case.", "audio", "2499.00", 25, "earbuds"),
            ("Core USB-C Charger", "A compact 30W USB-C wall charger.", "accessories", "899.00", 40, "charger"),
            ("Nova Lite Smartphone", "A dependable everyday phone with a long-lasting battery.", "smartphones", "9999.00", 20, "phones"),
            ("Orbit Book 15", "A practical 15-inch laptop with a comfortable keyboard.", "laptops", "32999.00", 6, "laptops"),
            ("Tab Mini 8", "A portable tablet that fits easily into your day bag.", "tablets", "8999.00", 14, "tablets"),
            ("Studio Bluetooth Speaker", "A portable speaker with clear, room-filling sound.", "audio", "3199.00", 16, "speakers"),
            ("Flex Protective Case", "A slim protective case for everyday bumps and scratches.", "accessories", "599.00", 35, "accessories"),
            ("Apple iPhone 18", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "69990.00", 6, "phones"),
            ("Apple iPhone 18 Pro", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "89990.00", 4, "phones"),
            ("Apple iPhone 17", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "59990.00", 7, "phones"),
            ("Apple iPhone 17 Pro", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "79990.00", 5, "phones"),
            ("Apple iPhone 16", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "49990.00", 8, "phones"),
            ("Apple iPhone 16 Pro", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "69990.00", 4, "phones"),
            ("Apple iPhone 15", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "39990.00", 9, "phones"),
            ("Apple iPhone 15 Pro", "Demo listing. Confirm current price, storage, and color options with the store.", "smartphones", "59990.00", 3, "phones"),
        ]
        category_map = {category.slug: category for category in categories}
        legacy_image_keys = {
            "phones": "phone",
            "laptops": "laptop",
            "tablets": "tablet",
            "speakers": "speaker",
            "accessories": "case",
        }
        added_products = 0
        for name, description, category_slug, price, stock, image_key in product_data:
            slug = models.make_slug(name)
            product = models.Product.query.filter_by(slug=slug).first()
            if product:
                legacy_image = legacy_image_keys.get(image_key, image_key)
                if product.image_path == f"products/{legacy_image}.svg":
                    product.image_path = f"products/{image_key}.jpg"
                continue
            db.session.add(models.Product(
                name=name,
                slug=slug,
                description=description,
                price=Decimal(price),
                stock=stock,
                category=category_map[category_slug],
                image_path=f"products/{image_key}.jpg",
                featured=stock > 10,
            ))
            added_products += 1
        db.session.commit()
        click.echo(f"Seed complete; added {added_products} missing demo products.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Administrator name")
    @click.option("--email", prompt="Administrator email")
    @click.option("--phone", prompt="Phone number")
    @click.password_option()
    def create_admin_command(name, email, phone, password):
        """Create an administrator account without storing a plain-text password."""
        email = email.strip().lower()
        if models.User.query.filter_by(email=email).first():
            raise click.ClickException("An account with that email already exists.")
        user = models.User(name=name.strip(), email=email, phone=phone.strip(), role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator account created for {email}.")

    from .errors import register_error_handlers
    register_error_handlers(app)
    return app
