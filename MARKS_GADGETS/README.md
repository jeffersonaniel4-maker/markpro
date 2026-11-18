# MARKS GADGETS

**Your Trusted Gadget Store** is a Flask storefront for gadgets, with customer accounts, a persistent database-backed cart, COD checkout, order history, product reviews, and a role-protected admin area.

## Requirements

- Windows 10/11
- Python 3.10 or later (include the Python Launcher, `py`)
- MySQL 8.0+ (or a compatible MariaDB release)
- Visual Studio Code

SQLite is used automatically for local development and automated tests when `DATABASE_URL` is not set. MySQL is the recommended shared/deployment database.

## Open in VS Code

Open the `MARKS_GADGETS` folder in VS Code. Open **Terminal → New Terminal** and run the commands below from the project root.

## Virtual environment and dependencies

In Windows Command Prompt:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `py` is not recognized, install Python from python.org and select **Add python.exe to PATH** and **Install launcher for all users** in the installer.
If Python is installed for your Windows user but PATH has not refreshed, use its executable directly in Command Prompt, for example:

```bat
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
```

## Use an existing MySQL database

To connect this application to an existing database named `markgadgets`, put its connection URL in `.env`:

```dotenv
DATABASE_URL=mysql+pymysql://your_user:your_password@localhost/markgadgets?charset=utf8mb4
```

Replace the example host, user, and password with the credentials for your MySQL server. Do not run `schema.sql`, `flask --app app.py init-db`, or `seed-demo` against an existing store database; those setup commands create tables or add demo data.

The local MySQL server and credentials are not included in this project folder, so the connection and the live schema cannot be verified here. The existing Flask storefront maps its core features to `users`, `categories`, `products`, `cart_items`, `orders`, `order_items`, `payments`, and `reviews`, with the columns in `schema.sql`. Admin pages discover optional tables such as `suppliers`, `inventory_logs`, `loyalty`, `notifications`, and `reports` without creating or changing them. When a separate `sales`/`sale_items` table is absent, those pages use the existing `orders`/`order_items` records; inventory is based on product stock, and customers fall back to customer-role rows in `users`. The connected database must have compatible core tables for the existing login, storefront, and dashboard ORM queries to run.

## Create a fresh MySQL database (optional)

Start the MySQL service, then create the database and an application user. Replace the example password with your own strong password and enter it at the MySQL prompt when requested:

```sql
CREATE DATABASE marks_gadgets_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'marks_user'@'localhost' IDENTIFIED BY 'use-a-unique-strong-password';
GRANT ALL PRIVILEGES ON marks_gadgets_db.* TO 'marks_user'@'localhost';
FLUSH PRIVILEGES;
```

Import the schema and sample catalog as a MySQL administrator (the SQL file creates the database):

```bat
mysql -u root -p < schema.sql
```

The Flask CLI can create tables from the SQLAlchemy models and seed sample products instead:

```bat
flask --app app.py init-db
flask --app app.py seed-demo
```

Use either the SQL import or `init-db` plus `seed-demo`. The seed command is safe to rerun and skips when categories already exist. For this fresh setup, set `DATABASE_URL` to the `marks_gadgets_db` database created above.

## Environment configuration

Copy the sample environment file, then edit `.env` in the project root:

```bat
copy .env.example .env
notepad .env
```

Set a long random `SECRET_KEY` and the MySQL connection string:

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=mysql+pymysql://marks_user:YOUR_PASSWORD@localhost/markgadgets?charset=utf8mb4
FLASK_DEBUG=1
```

If the database password contains URL-reserved characters, percent-encode it in `DATABASE_URL`. `.env` is ignored by Git. Never commit secrets.

For a quick SQLite-only demo, leave `DATABASE_URL` unset; the app uses `instance/marks_gadgets_dev.sqlite`.

## Create the first administrator

With the virtual environment active and `.env` configured, run:

```bat
flask --app app.py create-admin
```

Enter the administrator name, email, phone number, and password at the prompts. The password is entered through a hidden prompt and stored only as a Werkzeug hash. Then sign in at `http://127.0.0.1:5000/login`; administrators see the **Admin** link after login.

Do not promote a user by editing the role from an untrusted interface. Restrict direct database administration to trusted operators.

## Run the application

```bat
flask --app app.py run --debug
```

Open <http://127.0.0.1:5000>. To stop the development server, press `Ctrl+C` in the terminal.

## Run automated tests

Tests use an in-memory SQLite database and do not require a running MySQL server:

```bat
pytest -q
```

The tests cover registration/password hashing, duplicate accounts, bad credentials, product browsing, cart stock checks, admin authorization, server-calculated order totals, insufficient-stock checkout, and inventory/cart consistency.

## Implemented features

- Responsive storefront, category browsing, search, sort, pagination, product details, ratings and approved reviews
- Password-hashed accounts, Flask-Login sessions, CSRF-protected forms, customer profiles and order history
- Persistent customer carts with server-side quantity/stock validation
- Transactional Cash on Delivery orders with server-calculated totals, stock reduction and order references
- Admin product/category management, validated image uploads, inventory, order status changes, customer list, review moderation, and date-filtered verified COD collections
- Responsive admin sidebar with persistent collapse state, mobile navigation, searchable management lists, live dashboard metrics, revenue chart, and inventory summary
- Read-only discovery of optional admin tables; unavailable tables are reported without being created or altered
- MySQL schema and sample catalog; SQLite fallback for development and tests

Online payments (GCash/Maya/provider integrations) are **not implemented**. They are labeled as pending integration and cannot be selected at checkout. Contact email delivery is also not configured; the contact page opens an email to the listed support address. Product reviews require admin approval before they appear publicly.

## Troubleshooting

- **`py` or `python` not found:** install Python from python.org, enable PATH and the launcher, then open a new terminal.
- **`No module named ...`:** activate `.venv` and run `pip install -r requirements.txt`.
- **MySQL connection refused:** start the MySQL service and confirm host, port, user grants, and database name in `.env`.
- **Access denied:** verify the MySQL username/password and that the user has privileges on `markgadgets`.
- **Unknown database:** create the database or import `schema.sql` as shown above.
- **Images do not upload:** use a real JPG, PNG, or WebP under 4 MB; generated uploads are stored in the static product upload directory.
- **CSRF error:** submit forms through the app pages and ensure cookies are enabled. Do not disable CSRF outside isolated tests.

## Production checklist

- Set a unique, high-entropy `SECRET_KEY`; set `FLASK_DEBUG=0` and `COOKIE_SECURE=1` behind HTTPS.
- Use a least-privilege database account, TLS connections, regular backups, and a managed migration process.
- Serve through a production WSGI server behind a reverse proxy with HTTPS; do not use Flask's development server.
- Restrict and back up uploaded images; scan uploads and enforce storage limits appropriate to the deployment.
- Configure monitoring, log retention, email delivery, privacy/terms pages, shipping/tax rules, and a verified payment provider before enabling online payments.
- Review local privacy, consumer-protection, tax, and payment regulations before launch.
