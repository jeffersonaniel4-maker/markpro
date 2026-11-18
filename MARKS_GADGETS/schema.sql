CREATE DATABASE IF NOT EXISTS marks_gadgets_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE marks_gadgets_db;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  phone VARCHAR(30) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'customer',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX ix_users_role (role)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  slug VARCHAR(120) NOT NULL UNIQUE,
  description VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  category_id INT NOT NULL,
  name VARCHAR(180) NOT NULL,
  slug VARCHAR(200) NOT NULL UNIQUE,
  description TEXT NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  image_path VARCHAR(255) NOT NULL DEFAULT 'products/placeholder.svg',
  featured BOOLEAN NOT NULL DEFAULT FALSE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
  CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0),
  CONSTRAINT ck_products_stock_nonnegative CHECK (stock >= 0),
  INDEX ix_products_category_id (category_id),
  INDEX ix_products_name (name),
  INDEX ix_products_active (active)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cart_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_cart_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_cart_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT uq_cart_user_product UNIQUE (user_id, product_id),
  CONSTRAINT ck_cart_items_quantity_positive CHECK (quantity >= 1),
  INDEX ix_cart_items_user_id (user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  reference VARCHAR(24) NOT NULL UNIQUE,
  user_id INT NOT NULL,
  customer_name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NOT NULL,
  shipping_address VARCHAR(500) NOT NULL,
  notes VARCHAR(1000) NOT NULL DEFAULT '',
  total DECIMAL(10,2) NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  payment_method VARCHAR(30) NOT NULL DEFAULT 'cod',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT ck_orders_total_nonnegative CHECK (total >= 0),
  INDEX ix_orders_user_id (user_id),
  INDEX ix_orders_reference (reference),
  INDEX ix_orders_status (status),
  INDEX ix_orders_created_status (created_at, status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  product_name VARCHAR(180) NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  quantity INT NOT NULL,
  CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
  CONSTRAINT ck_order_items_quantity_positive CHECK (quantity >= 1),
  INDEX ix_order_items_order_id (order_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL UNIQUE,
  method VARCHAR(30) NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  provider_reference VARCHAR(120) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS reviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  rating INT NOT NULL,
  body VARCHAR(1500) NOT NULL,
  approved BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_reviews_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT ck_reviews_rating_range CHECK (rating >= 1 AND rating <= 5),
  CONSTRAINT uq_review_user_product UNIQUE (user_id, product_id),
  INDEX ix_reviews_user_id (user_id),
  INDEX ix_reviews_product_id (product_id)
) ENGINE=InnoDB;

INSERT IGNORE INTO categories (name, slug, description) VALUES
  ('Smartphones', 'smartphones', 'Phones for work, play, and everything between.'),
  ('Laptops', 'laptops', 'Portable computers for study and work.'),
  ('Tablets', 'tablets', 'Versatile screens for creativity and entertainment.'),
  ('Accessories', 'accessories', 'Everyday essentials for your devices.'),
  ('Audio', 'audio', 'Headphones, speakers, and more.');

INSERT IGNORE INTO products (category_id, name, slug, description, price, stock, image_path, featured, active)
SELECT c.id, p.name, p.slug, p.description, p.price, p.stock, p.image_path, p.featured, TRUE
FROM (
  SELECT 'Nova X5 Smartphone' name, 'nova-x5-smartphone' slug, 'A responsive 5G smartphone with a vivid OLED display.' description, 18999.00 price, 18 stock, 'products/phones.jpg' image_path, TRUE featured, 'smartphones' category_slug UNION ALL
  SELECT 'Orbit Pro 14 Laptop', 'orbit-pro-14-laptop', 'A lightweight laptop built for multitasking and study.', 42999.00, 8, 'products/laptops.jpg', FALSE, 'laptops' UNION ALL
  SELECT 'Tab Air 11', 'tab-air-11', 'An 11-inch tablet for reading, streaming, and sketching.', 16999.00, 12, 'products/tablets.jpg', TRUE, 'tablets' UNION ALL
  SELECT 'Pulse Wireless Earbuds', 'pulse-wireless-earbuds', 'Compact wireless earbuds with a charging case.', 2499.00, 25, 'products/earbuds.jpg', TRUE, 'audio' UNION ALL
  SELECT 'Core USB-C Charger', 'core-usb-c-charger', 'A compact 30W USB-C wall charger.', 899.00, 40, 'products/charger.jpg', TRUE, 'accessories' UNION ALL
  SELECT 'Nova Lite Smartphone', 'nova-lite-smartphone', 'A dependable everyday phone with a long-lasting battery.', 9999.00, 20, 'products/phones.jpg', TRUE, 'smartphones' UNION ALL
  SELECT 'Orbit Book 15', 'orbit-book-15', 'A practical 15-inch laptop with a comfortable keyboard.', 32999.00, 6, 'products/laptops.jpg', FALSE, 'laptops' UNION ALL
  SELECT 'Tab Mini 8', 'tab-mini-8', 'A portable tablet that fits easily into your day bag.', 8999.00, 14, 'products/tablets.jpg', TRUE, 'tablets' UNION ALL
  SELECT 'Studio Bluetooth Speaker', 'studio-bluetooth-speaker', 'A portable speaker with clear, room-filling sound.', 3199.00, 16, 'products/speakers.jpg', TRUE, 'audio' UNION ALL
  SELECT 'Flex Protective Case', 'flex-protective-case', 'A slim protective case for everyday bumps and scratches.', 599.00, 35, 'products/accessories.jpg', TRUE, 'accessories' UNION ALL
  SELECT 'Apple iPhone 18', 'apple-iphone-18', 'Demo listing. Confirm current price, storage, and color options with the store.', 69990.00, 6, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 18 Pro', 'apple-iphone-18-pro', 'Demo listing. Confirm current price, storage, and color options with the store.', 89990.00, 4, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 17', 'apple-iphone-17', 'Demo listing. Confirm current price, storage, and color options with the store.', 59990.00, 7, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 17 Pro', 'apple-iphone-17-pro', 'Demo listing. Confirm current price, storage, and color options with the store.', 79990.00, 5, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 16', 'apple-iphone-16', 'Demo listing. Confirm current price, storage, and color options with the store.', 49990.00, 8, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 16 Pro', 'apple-iphone-16-pro', 'Demo listing. Confirm current price, storage, and color options with the store.', 69990.00, 4, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 15', 'apple-iphone-15', 'Demo listing. Confirm current price, storage, and color options with the store.', 39990.00, 9, 'products/phones.jpg', FALSE, 'smartphones' UNION ALL
  SELECT 'Apple iPhone 15 Pro', 'apple-iphone-15-pro', 'Demo listing. Confirm current price, storage, and color options with the store.', 59990.00, 3, 'products/phones.jpg', FALSE, 'smartphones'
) AS p
JOIN categories c ON c.slug = p.category_slug;