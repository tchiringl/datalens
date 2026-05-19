-- =============================================================================
-- Retail AI Data Hub POC — PostgreSQL Seed File
-- =============================================================================
-- Schemas: public (retail), airflow (metadata), openmetadata (metadata)
-- =============================================================================

-- Create additional databases (run as superuser before connecting to each)
CREATE DATABASE airflow;
CREATE DATABASE openmetadata;
CREATE DATABASE om_airflow;  -- dedicated DB for OpenMetadata ingestion Airflow instance

-- =============================================================================
-- SCHEMA SETUP
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS public;

-- =============================================================================
-- DDL: CREATE TABLES
-- =============================================================================

CREATE TABLE countries (
  country_id   VARCHAR(2)  PRIMARY KEY,
  country_name VARCHAR(100),
  region       VARCHAR(50),
  currency_code VARCHAR(3)
);

CREATE TABLE stores (
  store_id       SERIAL PRIMARY KEY,
  store_code     VARCHAR(20)  UNIQUE NOT NULL,
  store_name     VARCHAR(100) NOT NULL,
  store_type     VARCHAR(20)  CHECK (store_type IN ('retail','outlet','online','flagship')),
  address        VARCHAR(200),
  city           VARCHAR(100),
  state_province VARCHAR(100),
  country_id     VARCHAR(2)   REFERENCES countries(country_id),
  zip_code       VARCHAR(20),
  phone          VARCHAR(20),
  email          VARCHAR(100),
  manager_name   VARCHAR(100),
  opened_date    DATE,
  is_active      BOOLEAN DEFAULT TRUE,
  square_footage INTEGER,
  created_at     TIMESTAMP DEFAULT NOW(),
  updated_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE product_categories (
  category_id        SERIAL PRIMARY KEY,
  category_name      VARCHAR(100) NOT NULL,
  parent_category_id INTEGER REFERENCES product_categories(category_id),
  description        TEXT,
  created_at         TIMESTAMP DEFAULT NOW()
);

CREATE TABLE suppliers (
  supplier_id   SERIAL PRIMARY KEY,
  supplier_name VARCHAR(200) NOT NULL,
  contact_name  VARCHAR(100),
  email         VARCHAR(100),
  phone         VARCHAR(20),
  address       VARCHAR(200),
  country_id    VARCHAR(2) REFERENCES countries(country_id),
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE products (
  product_id     SERIAL PRIMARY KEY,
  sku            VARCHAR(50)  UNIQUE NOT NULL,
  product_name   VARCHAR(200) NOT NULL,
  category_id    INTEGER REFERENCES product_categories(category_id),
  brand          VARCHAR(100),
  description    TEXT,
  unit_price     DECIMAL(10,2) NOT NULL,
  cost_price     DECIMAL(10,2),
  weight_kg      DECIMAL(8,3),
  is_active      BOOLEAN DEFAULT TRUE,
  stock_quantity INTEGER DEFAULT 0,
  reorder_level  INTEGER DEFAULT 10,
  supplier_id    INTEGER REFERENCES suppliers(supplier_id),
  created_at     TIMESTAMP DEFAULT NOW(),
  updated_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE customers (
  customer_id      SERIAL PRIMARY KEY,
  customer_code    VARCHAR(20)  UNIQUE NOT NULL,
  first_name       VARCHAR(100) NOT NULL,
  last_name        VARCHAR(100) NOT NULL,
  email            VARCHAR(200),  -- nullable: 50 NULLs intentional (DQ ISSUE 1)
  phone            VARCHAR(20),
  date_of_birth    DATE,
  gender           VARCHAR(10) CHECK (gender IN ('M','F','Other','Unknown')),
  address          VARCHAR(200),
  city             VARCHAR(100),
  state_province   VARCHAR(100),
  country_id       VARCHAR(2) REFERENCES countries(country_id),
  zip_code         VARCHAR(20),
  loyalty_tier     VARCHAR(20) CHECK (loyalty_tier IN ('Bronze','Silver','Gold','Platinum')) DEFAULT 'Bronze',
  loyalty_points   INTEGER DEFAULT 0,
  is_active        BOOLEAN DEFAULT TRUE,
  acquired_channel VARCHAR(30) CHECK (acquired_channel IN ('organic','paid_search','social','referral','email','in_store')),
  created_at       TIMESTAMP DEFAULT NOW(),
  updated_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE promotions (
  promo_id          SERIAL PRIMARY KEY,
  promo_code        VARCHAR(30) UNIQUE NOT NULL,
  description       VARCHAR(200),
  discount_type     VARCHAR(20) CHECK (discount_type IN ('percentage','fixed','bogo','free_shipping')),
  discount_value    DECIMAL(8,2),
  min_order_amount  DECIMAL(10,2),
  start_date        DATE,
  end_date          DATE,
  usage_limit       INTEGER,
  times_used        INTEGER DEFAULT 0,
  is_active         BOOLEAN DEFAULT TRUE,
  created_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
  order_id           SERIAL PRIMARY KEY,
  order_code         VARCHAR(30) NOT NULL,  -- NOT UNIQUE: has duplicates (DQ ISSUE 2)
  customer_id        INTEGER REFERENCES customers(customer_id),
  store_id           INTEGER REFERENCES stores(store_id),
  order_date         TIMESTAMP NOT NULL,
  status             VARCHAR(20) CHECK (status IN ('pending','processing','shipped','delivered','cancelled','returned')),
  payment_method     VARCHAR(30) CHECK (payment_method IN ('credit_card','debit_card','paypal','apple_pay','google_pay','cash','gift_card')),
  shipping_address   VARCHAR(200),
  shipping_city      VARCHAR(100),
  shipping_country_id VARCHAR(2),
  subtotal           DECIMAL(12,2),
  discount_amount    DECIMAL(10,2) DEFAULT 0,
  shipping_cost      DECIMAL(8,2)  DEFAULT 0,
  tax_amount         DECIMAL(10,2) DEFAULT 0,
  total_amount       DECIMAL(12,2),
  currency_code      VARCHAR(3) DEFAULT 'USD',
  promo_code         VARCHAR(30),
  notes              TEXT,
  created_at         TIMESTAMP DEFAULT NOW(),
  updated_at         TIMESTAMP DEFAULT NOW()
);

CREATE TABLE order_items (
  order_item_id SERIAL PRIMARY KEY,
  order_id      INTEGER REFERENCES orders(order_id),
  product_id    INTEGER REFERENCES products(product_id),
  quantity      INTEGER       NOT NULL CHECK (quantity > 0),
  unit_price    DECIMAL(10,2) NOT NULL,
  discount_pct  DECIMAL(5,2)  DEFAULT 0,
  line_total    DECIMAL(12,2),
  created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE returns (
  return_id     SERIAL PRIMARY KEY,
  order_id      INTEGER REFERENCES orders(order_id),
  order_item_id INTEGER REFERENCES order_items(order_item_id),
  return_date   TIMESTAMP NOT NULL,
  reason        VARCHAR(50) CHECK (reason IN ('defective','wrong_item','not_as_described','changed_mind','damaged_shipping','other')),
  status        VARCHAR(20) CHECK (status IN ('requested','approved','received','refunded','rejected')),
  refund_amount DECIMAL(10,2),
  notes         TEXT,
  created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE employees (
  employee_id   SERIAL PRIMARY KEY,
  employee_code VARCHAR(20)  UNIQUE NOT NULL,
  first_name    VARCHAR(100) NOT NULL,
  last_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(200),
  role          VARCHAR(50) CHECK (role IN ('store_manager','sales_associate','warehouse','analyst','manager','director')),
  store_id      INTEGER REFERENCES stores(store_id),
  hire_date     DATE,
  salary        DECIMAL(10,2),
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE inventory_snapshots (
  snapshot_id       SERIAL PRIMARY KEY,
  product_id        INTEGER REFERENCES products(product_id),
  store_id          INTEGER REFERENCES stores(store_id),
  snapshot_date     DATE NOT NULL,
  quantity_on_hand  INTEGER,
  quantity_reserved INTEGER DEFAULT 0,
  reorder_triggered BOOLEAN DEFAULT FALSE,
  created_at        TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- SEED DATA: COUNTRIES (20 rows)
-- =============================================================================
INSERT INTO countries (country_id, country_name, region, currency_code) VALUES
  ('US', 'United States',    'North America', 'USD'),
  ('CA', 'Canada',           'North America', 'CAD'),
  ('GB', 'United Kingdom',   'Europe',        'GBP'),
  ('AU', 'Australia',        'Oceania',       'AUD'),
  ('DE', 'Germany',          'Europe',        'EUR'),
  ('FR', 'France',           'Europe',        'EUR'),
  ('JP', 'Japan',            'Asia',          'JPY'),
  ('CN', 'China',            'Asia',          'CNY'),
  ('IN', 'India',            'Asia',          'INR'),
  ('BR', 'Brazil',           'South America', 'BRL'),
  ('MX', 'Mexico',           'North America', 'MXN'),
  ('IT', 'Italy',            'Europe',        'EUR'),
  ('ES', 'Spain',            'Europe',        'EUR'),
  ('NL', 'Netherlands',      'Europe',        'EUR'),
  ('SE', 'Sweden',           'Europe',        'SEK'),
  ('KR', 'South Korea',      'Asia',          'KRW'),
  ('SG', 'Singapore',        'Asia',          'SGD'),
  ('ZA', 'South Africa',     'Africa',        'ZAR'),
  ('NZ', 'New Zealand',      'Oceania',       'NZD'),
  ('AE', 'United Arab Emirates','Middle East','AED');

-- =============================================================================
-- SEED DATA: STORES (30 rows)
-- =============================================================================
INSERT INTO stores (store_code, store_name, store_type, address, city, state_province, country_id, zip_code, phone, email, manager_name, opened_date, is_active, square_footage) VALUES
-- USA (15 stores)
('US-NYC-001', 'Manhattan Flagship',      'flagship', '500 Fifth Avenue',          'New York',      'New York',          'US', '10110', '+1-212-555-0101', 'nyc.flagship@retailhub.com',    'James Patterson',   '2015-03-15', TRUE,  18000),
('US-LAX-001', 'Los Angeles Retail',      'retail',   '8500 Beverly Blvd',         'Los Angeles',   'California',        'US', '90048', '+1-323-555-0102', 'la.retail@retailhub.com',       'Maria Gonzalez',    '2016-06-01', TRUE,  12000),
('US-CHI-001', 'Chicago Downtown',        'retail',   '900 N Michigan Ave',        'Chicago',       'Illinois',          'US', '60611', '+1-312-555-0103', 'chicago@retailhub.com',         'Robert Chen',       '2017-01-10', TRUE,  10500),
('US-HOU-001', 'Houston Galleria',        'retail',   '5085 Westheimer Rd',        'Houston',       'Texas',             'US', '77056', '+1-713-555-0104', 'houston@retailhub.com',         'Sandra Williams',   '2017-08-22', TRUE,  9800),
('US-PHX-001', 'Phoenix Scottsdale',      'retail',   '7014 E Camelback Rd',       'Scottsdale',    'Arizona',           'US', '85251', '+1-480-555-0105', 'phoenix@retailhub.com',         'Thomas Baker',      '2018-03-05', TRUE,  8500),
('US-PHI-001', 'Philadelphia Center',     'retail',   '1600 Market Street',        'Philadelphia',  'Pennsylvania',      'US', '19103', '+1-215-555-0106', 'philly@retailhub.com',          'Angela Martinez',   '2018-09-12', TRUE,  9200),
('US-SEA-001', 'Seattle Pike Place',      'retail',   '1500 Pike Place',           'Seattle',       'Washington',        'US', '98101', '+1-206-555-0107', 'seattle@retailhub.com',         'Kevin O''Brien',    '2019-02-14', TRUE,  8800),
('US-DEN-001', 'Denver Cherry Creek',     'retail',   '3000 E 1st Ave',            'Denver',        'Colorado',          'US', '80206', '+1-303-555-0108', 'denver@retailhub.com',          'Lisa Thompson',     '2019-07-01', TRUE,  8200),
('US-ATL-001', 'Atlanta Perimeter',       'retail',   '4400 Ashford Dunwoody Rd',  'Atlanta',       'Georgia',           'US', '30346', '+1-770-555-0109', 'atlanta@retailhub.com',         'Marcus Johnson',    '2020-01-15', TRUE,  9500),
('US-MIA-001', 'Miami Brickell',          'flagship', '1111 Brickell Ave',         'Miami',         'Florida',           'US', '33131', '+1-305-555-0110', 'miami.flagship@retailhub.com',  'Sofia Perez',       '2016-11-01', TRUE,  15000),
('US-BOS-001', 'Boston Newbury Street',   'retail',   '200 Newbury St',            'Boston',        'Massachusetts',     'US', '02116', '+1-617-555-0111', 'boston@retailhub.com',          'Daniel Walsh',      '2018-05-20', TRUE,  8000),
('US-LAS-001', 'Las Vegas Strip Outlet',  'outlet',   '3663 Las Vegas Blvd S',     'Las Vegas',     'Nevada',            'US', '89109', '+1-702-555-0112', 'lasvegas@retailhub.com',        'Jennifer Kim',      '2017-12-01', TRUE,  11000),
('US-POR-001', 'Portland Pearl District', 'retail',   '1000 NW Couch St',          'Portland',      'Oregon',            'US', '97209', '+1-503-555-0113', 'portland@retailhub.com',        'Aaron Mitchell',    '2020-08-10', TRUE,  7500),
('US-MIN-001', 'Minneapolis Mall of America','outlet', '60 E Broadway',            'Bloomington',   'Minnesota',         'US', '55425', '+1-952-555-0114', 'minneapolis@retailhub.com',     'Rachel Anderson',   '2019-10-01', TRUE,  12500),
('US-ONL-001', 'US Online Store',         'online',   '1 Digital Way',             'Austin',        'Texas',             'US', '78701', '+1-512-555-0115', 'online.us@retailhub.com',       'Chris Digital',     '2014-01-01', TRUE,  0),
-- UK (5 stores)
('GB-LON-001', 'London Oxford Street',    'flagship', '350 Oxford Street',         'London',        'England',           'GB', 'W1C 1JN', '+44-20-5550101', 'london.flagship@retailhub.com', 'Emma Thompson',    '2016-04-01', TRUE,  14000),
('GB-MCR-001', 'Manchester Arndale',      'retail',   '49 High St',                'Manchester',    'England',           'GB', 'M4 3AH',  '+44-161-555-0102','manchester@retailhub.com',      'Liam Davies',      '2018-03-15', TRUE,  9000),
('GB-BIR-001', 'Birmingham Bullring',     'retail',   '35 Bullring',               'Birmingham',    'England',           'GB', 'B5 4BU',  '+44-121-555-0103','birmingham@retailhub.com',      'Charlotte Evans',  '2019-06-01', TRUE,  8500),
('GB-EDI-001', 'Edinburgh Royal Mile',    'retail',   '47 Royal Mile',             'Edinburgh',     'Scotland',          'GB', 'EH1 1SR', '+44-131-555-0104','edinburgh@retailhub.com',       'Hamish MacLeod',   '2020-01-10', TRUE,  7000),
('GB-ONL-001', 'UK Online Store',         'online',   '1 Digital Square',          'London',        'England',           'GB', 'EC1A 1BB','+44-20-5550105', 'online.uk@retailhub.com',       'Oliver Digital',   '2015-06-01', TRUE,  0),
-- Canada (5 stores)
('CA-TOR-001', 'Toronto Eaton Centre',    'retail',   '220 Yonge St',              'Toronto',       'Ontario',           'CA', 'M5B 2H1', '+1-416-555-0101', 'toronto@retailhub.com',        'Sarah MacDonald',   '2017-09-01', TRUE,  10000),
('CA-VAN-001', 'Vancouver Pacific Centre','flagship', '701 W Georgia St',          'Vancouver',     'British Columbia',  'CA', 'V7Y 1G5', '+1-604-555-0102', 'vancouver.flagship@retailhub.com','Brian Nguyen',   '2016-05-15', TRUE,  13000),
('CA-MTL-001', 'Montreal Laurier',        'retail',   '5075 Ave Laurier O',        'Montreal',      'Quebec',            'CA', 'H2V 2L1', '+1-514-555-0103', 'montreal@retailhub.com',        'Marie Tremblay',    '2018-11-01', TRUE,  8800),
('CA-CAL-001', 'Calgary Market Mall',     'retail',   '3625 Shaganappi Trail NW',  'Calgary',       'Alberta',           'CA', 'T3A 0E2', '+1-403-555-0104', 'calgary@retailhub.com',         'Jake Wilson',       '2019-04-01', TRUE,  9200),
('CA-OTT-001', 'Ottawa Rideau Centre',    'retail',   '50 Rideau St',              'Ottawa',        'Ontario',           'CA', 'K1N 9J7', '+1-613-555-0105', 'ottawa@retailhub.com',          'Diane Fortin',      '2020-03-01', TRUE,  8000),
-- Australia (5 stores)
('AU-SYD-001', 'Sydney CBD Flagship',     'flagship', '188 Pitt Street',           'Sydney',        'New South Wales',   'AU', '2000',    '+61-2-5550-0101', 'sydney.flagship@retailhub.com', 'Jack Morrison',    '2016-08-01', TRUE,  13500),
('AU-MEL-001', 'Melbourne Collins St',    'retail',   '295 Collins Street',        'Melbourne',     'Victoria',          'AU', '3000',    '+61-3-5550-0102', 'melbourne@retailhub.com',       'Olivia Roberts',   '2017-11-01', TRUE,  10000),
('AU-BRI-001', 'Brisbane Queen Street',   'retail',   '226 Queen Street Mall',     'Brisbane',      'Queensland',        'AU', '4000',    '+61-7-5550-0103', 'brisbane@retailhub.com',        'Noah Campbell',    '2018-07-01', TRUE,  8500),
('AU-PER-001', 'Perth Hay Street',        'retail',   '622 Hay Street Mall',       'Perth',         'Western Australia', 'AU', '6000',    '+61-8-5550-0104', 'perth@retailhub.com',           'Ava Mitchell',     '2019-09-01', TRUE,  8000),
('AU-ADL-001', 'Adelaide Rundle Mall',    'outlet',   '80 Rundle Mall',            'Adelaide',      'South Australia',   'AU', '5000',    '+61-8-5550-0105', 'adelaide@retailhub.com',        'Ethan Clarke',     '2020-05-01', TRUE,  7500);

-- =============================================================================
-- SEED DATA: PRODUCT CATEGORIES (15 rows, with hierarchy)
-- =============================================================================
INSERT INTO product_categories (category_name, parent_category_id, description) VALUES
-- Top-level (parent_category_id = NULL)
('Electronics',     NULL, 'Consumer electronics including TVs, phones, laptops and accessories'),
('Clothing',        NULL, 'Apparel for men, women and children including footwear'),
('Home & Garden',   NULL, 'Furniture, decor, kitchen appliances and garden supplies'),
('Sports & Outdoors', NULL, 'Sporting equipment, activewear and outdoor gear'),
('Beauty & Personal Care', NULL, 'Skincare, haircare, cosmetics and grooming products'),
-- Electronics sub-categories (parent = 1)
('Televisions',     1, 'Smart TVs, OLED, QLED and LED displays'),
('Smartphones',     1, 'Mobile phones and accessories'),
('Laptops & Computers', 1, 'Notebooks, desktops and peripherals'),
-- Clothing sub-categories (parent = 2)
('Men''s Apparel',  2, 'Shirts, trousers, suits and men''s outerwear'),
('Women''s Apparel',2, 'Dresses, tops, skirts and women''s outerwear'),
('Footwear',        2, 'Sneakers, boots, sandals and formal shoes'),
-- Home sub-categories (parent = 3)
('Kitchen Appliances', 3, 'Coffee makers, blenders, air fryers and small appliances'),
('Furniture',       3, 'Sofas, beds, tables, chairs and storage solutions'),
-- Sports sub-categories (parent = 4)
('Fitness Equipment', 4, 'Weights, resistance bands, yoga mats and gym equipment'),
('Outdoor Gear',    4, 'Camping, hiking, cycling and water sports equipment');

-- =============================================================================
-- SEED DATA: SUPPLIERS (20 rows)
-- =============================================================================
INSERT INTO suppliers (supplier_name, contact_name, email, phone, address, country_id, is_active) VALUES
('TechSource Global Ltd',        'Alan Park',         'alan.park@techsource.com',       '+82-2-555-0101', '142 Teheran-ro, Gangnam-gu',          'KR', TRUE),
('Samsung Electronics Corp',     'Ji-ho Shin',        'jihoshin@samsung-supply.com',    '+82-2-555-0102', '129 Samsung-ro, Yeongtong-gu',        'KR', TRUE),
('Nike Supply Chain Inc',        'Brenda Collins',    'bcollins@nike-supply.com',       '+1-503-555-0201', '1 Bowerman Drive',                   'US', TRUE),
('Adidas International GmbH',    'Klaus Weber',       'kweber@adidas-supply.com',       '+49-9132-555-01', 'Adi-Dassler-Strasse 1',              'DE', TRUE),
('Apple Inc Wholesale',          'Megan Torres',      'mtorres@apple-supply.com',       '+1-408-555-0301', '1 Apple Park Way',                   'US', TRUE),
('Sony Electronics Ltd',         'Takashi Mori',      'tmori@sony-supply.com',          '+81-3-555-0401', '1-7-1 Konan, Minato-ku',             'JP', TRUE),
('H&M Group Wholesale',          'Anna Lindqvist',    'alindqvist@hm-wholesale.com',    '+46-8-555-0501', 'Mäster Samuelsgatan 46A',            'SE', TRUE),
('Philips Consumer Lifestyle',   'Jan de Vries',      'jdevries@philips-supply.com',    '+31-40-555-0601', 'High Tech Campus 5',                 'NL', TRUE),
('Unilever Supply Co',           'Rachel Patel',      'rpatel@unilever-supply.com',     '+44-20-555-0701', '100 Victoria Embankment',            'GB', TRUE),
('Bosch Home Appliances',        'Dieter Müller',     'dmuller@bosch-supply.com',       '+49-711-555-0801', 'Robert-Bosch-Platz 1',              'DE', TRUE),
('Zara Inditex Wholesale',       'Carmen Ruiz',       'cruiz@inditex-supply.com',       '+34-981-555-0901', 'Avenida de la Diputación',          'ES', TRUE),
('LG Electronics Supply',        'Soo-young Han',     'syhan@lg-supply.com',            '+82-2-555-1001', '128 Yeoui-daero, Yeongdeungpo-gu',   'KR', TRUE),
('Coleman Outdoor Products',     'Tyler Brooks',      'tbrooks@coleman-supply.com',     '+1-316-555-1101', '3600 N Hydraulic Ave',               'US', TRUE),
('L''Oreal Paris Wholesale',     'Sophie Dupont',     'sdupont@loreal-supply.com',      '+33-1-555-1201', '41 Rue Martre',                      'FR', TRUE),
('Reebok International',         'Michael Grant',     'mgrant@reebok-supply.com',       '+1-781-555-1301', '25 Drydock Avenue',                  'US', TRUE),
('IKEA Supply AG',               'Lars Johansson',    'ljohansson@ikea-supply.com',     '+46-476-555-14', 'IKEA-vägen 1',                       'SE', TRUE),
('Dyson Ltd',                    'James Cooling',     'jcooling@dyson-supply.com',      '+44-1666-555-15', 'Tetbury Hill',                      'GB', TRUE),
('New Balance Athletics',        'Patricia Stone',    'pstone@newbalance-supply.com',   '+1-617-555-1601', '100 Guest Street',                   'US', TRUE),
('Panasonic Corporation',        'Hiroshi Tanaka',    'htanaka@panasonic-supply.com',   '+81-6-555-1701', '3-1-1 Yagumo-Nakamachi',             'JP', TRUE),
('Under Armour Inc',             'Kevin Plank Jr',    'kplank@underarmour-supply.com',  '+1-410-555-1801', '1 Under Armour Way',                 'US', TRUE);

-- =============================================================================
-- SEED DATA: PRODUCTS (200 rows)
-- =============================================================================
INSERT INTO products (sku, product_name, category_id, brand, description, unit_price, cost_price, weight_kg, is_active, stock_quantity, reorder_level, supplier_id) VALUES
-- TELEVISIONS (category_id=6) ~20 products
('TV-SAM-65Q90', 'Samsung 65" QLED 4K Smart TV QN90B',6,'Samsung','Neo QLED 4K with Quantum Matrix Technology, 120Hz, HDR2000',1299.99,780.00,28.500,TRUE,45,5,2),
('TV-SAM-55Q80', 'Samsung 55" QLED 4K Smart TV QN80B',6,'Samsung','QLED 4K, Quantum Processor 4K, Object Tracking Sound',899.99,530.00,18.200,TRUE,62,5,2),
('TV-LG-65C3',   'LG 65" OLED evo C3 4K Smart TV',   6,'LG','OLED evo panel, a9 AI Processor Gen6, Dolby Vision IQ',1499.99,910.00,21.800,TRUE,30,5,12),
('TV-LG-55C3',   'LG 55" OLED evo C3 4K Smart TV',   6,'LG','OLED evo, 120Hz, G-Sync Compatible, Dolby Atmos',1199.99,720.00,15.600,TRUE,38,5,12),
('TV-SON-65X95', 'Sony 65" BRAVIA XR X95L Mini LED', 6,'Sony','Mini LED, XR Backlight Master Drive, Triluminos Pro',1399.99,840.00,26.200,TRUE,25,5,6),
('TV-SON-55A80', 'Sony 55" BRAVIA XR A80L OLED',     6,'Sony','OLED, XR Cognitive Processor, Acoustic Surface Audio+',1249.99,748.00,18.900,TRUE,20,5,6),
('TV-PHI-50PUS', 'Philips 50" The One 4K Ambilight',  6,'Philips','4-sided Ambilight, P5 AI Perfect Picture Engine',699.99,415.00,12.400,TRUE,55,8,8),
('TV-SAM-75Q70', 'Samsung 75" QLED 4K Smart TV Q70B',6,'Samsung','QLED 4K, Dual LED, Motion Xcelerator Turbo+',1099.99,660.00,35.800,TRUE,18,3,2),
('TV-LG-75UR91', 'LG 75" UHD 4K Smart TV UR9100',   6,'LG','4K UHD, α5 AI Processor Gen6, HDR10 Pro',699.99,415.00,28.900,TRUE,40,5,12),
('TV-PAN-65LZ20','Panasonic 65" OLED 4K TX-65LZ2000',6,'Panasonic','OLED, HCX Pro AI Processor MK2, Calman Verified',1599.99,960.00,22.100,TRUE,15,3,19),
-- SMARTPHONES (category_id=7) ~25 products
('PH-APL-IP15PM','Apple iPhone 15 Pro Max 256GB',    7,'Apple','A17 Pro chip, 48MP camera system, Titanium design',1199.99,700.00,0.221,TRUE,150,20,5),
('PH-APL-IP15P', 'Apple iPhone 15 Pro 128GB',        7,'Apple','A17 Pro chip, Super Retina XDR display, USB-C',999.99,590.00,0.187,TRUE,180,20,5),
('PH-APL-IP15',  'Apple iPhone 15 128GB',            7,'Apple','A16 Bionic, Dynamic Island, 48MP main camera',799.99,470.00,0.171,TRUE,220,25,5),
('PH-APL-IP14',  'Apple iPhone 14 128GB',            7,'Apple','A15 Bionic, Crash Detection, Emergency SOS',699.99,410.00,0.172,TRUE,95,15,5),
('PH-SAM-S24U',  'Samsung Galaxy S24 Ultra 256GB',   7,'Samsung','Snapdragon 8 Gen 3, 200MP camera, S Pen included',1299.99,760.00,0.232,TRUE,120,15,2),
('PH-SAM-S24P',  'Samsung Galaxy S24+ 256GB',        7,'Samsung','Snapdragon 8 Gen 3, 50MP triple camera, 4900mAh',999.99,585.00,0.196,TRUE,140,20,2),
('PH-SAM-S24',   'Samsung Galaxy S24 128GB',         7,'Samsung','Snapdragon 8 Gen 3, 50MP main, Bright Display',799.99,468.00,0.167,TRUE,175,20,2),
('PH-SAM-A55',   'Samsung Galaxy A55 5G 128GB',      7,'Samsung','Exynos 1480, 50MP OIS camera, 5000mAh battery',449.99,260.00,0.213,TRUE,200,25,2),
('PH-SON-XP5II', 'Sony Xperia 5 V 128GB',            7,'Sony','Snapdragon 8 Gen 2, 4K HDR OLED, 3.5mm jack',899.99,528.00,0.182,TRUE,60,10,6),
('PH-SAM-ZF5',   'Samsung Galaxy Z Fold5 256GB',     7,'Samsung','Foldable 7.6" display, Snapdragon 8 Gen 2',1799.99,1060.00,0.253,TRUE,45,5,2),
('PH-SAM-ZFL5',  'Samsung Galaxy Z Flip5 256GB',     7,'Samsung','Flip foldable, 3.4" FlexWindow, Snapdragon 8 Gen 2',999.99,588.00,0.187,TRUE,55,8,2),
('PH-APL-IP15M', 'Apple iPhone 15 Plus 256GB',       7,'Apple','6.7" Super Retina XDR, A16 Bionic, USB-C',899.99,529.00,0.201,TRUE,110,15,5),
('PH-SAM-A35',   'Samsung Galaxy A35 5G 128GB',      7,'Samsung','Exynos 1380, 50MP triple camera, IP67',349.99,200.00,0.210,TRUE,230,30,2),
('PH-SON-XP1V',  'Sony Xperia 1 V 256GB',            7,'Sony','Snapdragon 8 Gen 2, 4K 120Hz OLED, Zeiss T* optics',1099.99,649.00,0.187,TRUE,35,5,6),
('PH-APL-IPSE3', 'Apple iPhone SE 3rd Gen 64GB',     7,'Apple','A15 Bionic, Touch ID, 4.7" Retina display',429.99,252.00,0.144,TRUE,160,20,5),
-- LAPTOPS & COMPUTERS (category_id=8) ~20 products
('LT-APL-MBP14', 'Apple MacBook Pro 14" M3 Pro',     8,'Apple','M3 Pro chip, 18GB RAM, 512GB SSD, Liquid Retina XDR',1999.99,1180.00,1.610,TRUE,80,10,5),
('LT-APL-MBA15', 'Apple MacBook Air 15" M3',         8,'Apple','M3 chip, 8GB RAM, 256GB SSD, 15.3" Liquid Retina',1299.99,762.00,1.510,TRUE,95,10,5),
('LT-APL-MBA13', 'Apple MacBook Air 13" M2',         8,'Apple','M2 chip, 8GB RAM, 256GB SSD, MagSafe charging',1099.99,645.00,1.240,TRUE,110,12,5),
('LT-SAM-GBP15', 'Samsung Galaxy Book3 Pro 15.6"',   8,'Samsung','Intel Core i7-1360P, 16GB, 512GB NVMe, 2.8K AMOLED',1349.99,798.00,1.560,TRUE,50,8,2),
('LT-SON-VP15',  'Sony VAIO SX14 Intel Core i7',     8,'Sony','Core i7-1355U, 16GB, 512GB SSD, 14" IPS, 990g',1499.99,885.00,0.990,TRUE,30,5,6),
('LT-APL-MBPM16','Apple MacBook Pro 16" M3 Max',     8,'Apple','M3 Max, 36GB RAM, 1TB SSD, Liquid Retina XDR',3499.99,2060.00,2.140,TRUE,25,3,5),
('LT-SAM-GBU13', 'Samsung Galaxy Book3 Ultra 13.3"', 8,'Samsung','Intel Core i9, 32GB, 1TB SSD, Arc GPU, 3K AMOLED',2199.99,1298.00,1.390,TRUE,20,3,2),
('LT-SON-VZ14',  'Sony VAIO Z 14" Laptop',           8,'Sony','Intel Core i7, 16GB, 1TB SSD, CNC Aluminium',1799.99,1060.00,0.958,TRUE,18,3,6),
-- MEN'S APPAREL (category_id=9) ~20 products
('MA-NIK-ACTOP', 'Nike Dri-FIT ADV Running Top',     9,'Nike','Advanced Dri-FIT technology, reflective details',65.00,28.00,0.180,TRUE,300,30,3),
('MA-ADI-ULTRASH','Adidas Ultraboost Running Jacket', 9,'Adidas','Wind-resistant AEROREADY, recycled materials',120.00,52.00,0.380,TRUE,200,25,4),
('MA-NIK-TECHFL', 'Nike Tech Fleece Full Zip Hoodie', 9,'Nike','Lightweight fleece, tapered fit, zippered pockets',130.00,56.00,0.520,TRUE,180,20,3),
('MA-ADI-TIRO23', 'Adidas Tiro 23 League Track Jacket',9,'Adidas','Slim fit, woven fabric, embroidered logo',55.00,24.00,0.320,TRUE,250,30,4),
('MA-UAR-COLDG',  'Under Armour ColdGear Crew',       9,'Under Armour','ColdGear® infrared technology, anti-odor',65.00,29.00,0.290,TRUE,220,25,20),
('MA-NIK-JOGGER', 'Nike Sportswear Club Fleece Joggers',9,'Nike','Brushed fleece, elastic waistband, ribbed cuffs',65.00,28.00,0.420,TRUE,260,30,3),
('MA-ADI-ESSTHS', 'Adidas Essentials French Terry 3-Stripes Shorts',9,'Adidas','French terry cotton blend, contrast 3-Stripes',35.00,15.00,0.220,TRUE,320,35,4),
('MA-UAR-RUSH2',  'Under Armour RUSH 2.0 Compression Shirt',9,'Under Armour','Moisture-wicking, 4-way stretch, anti-odor',55.00,24.00,0.210,TRUE,280,30,20),
('MA-NIK-CHALL',  'Nike Challenger Woven Running Shorts',9,'Nike','Dri-FIT fabric, 7" inseam, liner brief',40.00,17.00,0.180,TRUE,300,35,3),
('MA-RBK-CLASSJ', 'Reebok Classic Leather Jacket',    9,'Reebok','100% genuine leather, quilted lining, vintage logo',189.99,85.00,0.980,TRUE,80,10,15),
-- WOMEN'S APPAREL (category_id=10) ~20 products
('WA-NIK-ONELUXT','Nike One Luxe Dri-FIT Training Tee',10,'Nike','Standard fit, soft Dri-FIT fabric, dropped hem',45.00,19.00,0.160,TRUE,280,30,3),
('WA-ADI-BELLIB', 'Adidas Believe This 2.0 Tights',   10,'Adidas','High waist, 7/8 length, moisture-absorbing fabric',60.00,26.00,0.230,TRUE,250,28,4),
('WA-NIK-EPOCHD', 'Nike Epic Luxe Crop Running Tights',10,'Nike','Mid-rise, 7/8 length, moisture-wicking with pockets',90.00,39.00,0.240,TRUE,200,22,3),
('WA-HM-STDRESS', 'H&M Studio Wrap Midi Dress',       10,'H&M','Crinkled texture, tie-belt, below-knee length',59.99,22.00,0.380,TRUE,180,20,7),
('WA-HM-LINBLZ',  'H&M Linen-Blend Blazer',           10,'H&M','Oversized fit, linen blend, structured shoulders',69.99,28.00,0.540,TRUE,150,18,7),
('WA-ZAR-FLODRE', 'Zara Flowy Print Midi Dress',      10,'Zara','V-neckline, flutter sleeves, floral print',49.99,18.00,0.320,TRUE,200,22,11),
('WA-ZAR-CROPJK', 'Zara Cropped Leather Jacket',      10,'Zara','Faux leather, asymmetric zip, boxy cut',89.99,35.00,0.760,TRUE,130,15,11),
('WA-ADI-PRIMAL', 'Adidas Primeblue Pacer 3-Stripes',10,'Adidas','Slim fit joggers, recycled Primeblue material',70.00,30.00,0.340,TRUE,220,25,4),
('WA-NIK-YOGAMAT','Nike Yoga Luxe Infinalon Shorts',   10,'Nike','7" inseam, Dri-FIT Infinalon fabric, lined',55.00,24.00,0.190,TRUE,240,28,3),
('WA-RBK-CLASST', 'Reebok Classic Vector Tee',        10,'Reebok','Cotton jersey, oversized fit, embroidered logo',30.00,12.00,0.170,TRUE,300,35,15),
-- FOOTWEAR (category_id=11) ~25 products
('FW-NIK-AM270',  'Nike Air Max 270 Men''s',          11,'Nike','React foam midsole, 270° Max Air unit, mesh upper',150.00,67.00,0.570,TRUE,200,20,3),
('FW-NIK-PEGASUS','Nike Air Zoom Pegasus 40',          11,'Nike','Dual-density foam, Air Zoom units, engineered mesh',130.00,58.00,0.490,TRUE,220,22,3),
('FW-ADI-ULTRA22','Adidas Ultraboost 22',              11,'Adidas','Boost midsole, Primeknit+ upper, Continental rubber',180.00,82.00,0.620,TRUE,190,20,4),
('FW-ADI-SAMBA',  'Adidas Samba OG Shoes',            11,'Adidas','Suede upper, rubber sole, iconic T-toe design',100.00,44.00,0.450,TRUE,250,25,4),
('FW-NIK-JORDAN1','Nike Air Jordan 1 Retro High OG',  11,'Nike','Leather upper, Air-Sole unit, rubber outsole',180.00,80.00,0.640,TRUE,120,15,3),
('FW-RBK-CLASSLT','Reebok Classic Leather Sneakers',  11,'Reebok','Full-grain leather, soft foam sockliner, low-cut',85.00,37.00,0.380,TRUE,230,25,15),
('FW-NIK-FREERUN','Nike Free RN 5.0 Next Nature',     11,'Nike','Flex grooves, Flyknit, minimal, lightweight',110.00,49.00,0.240,TRUE,180,20,3),
('FW-ADI-NMD_R1', 'Adidas NMD_R1 Shoes',             11,'Adidas','Boost cushioning, Primeknit, EVA pods',130.00,57.00,0.490,TRUE,160,18,4),
('FW-NB-990V6',   'New Balance 990v6 Running Shoe',   11,'New Balance','ENCAP midsole, pigskin suede, Made in USA',185.00,84.00,0.570,TRUE,100,12,18),
('FW-UAR-HOVERM', 'Under Armour HOVR Machina 3 Men''s',11,'Under Armour','UA HOVR technology, OrthoLite® insole, mesh',130.00,57.00,0.480,TRUE,140,15,20),
('FW-NIK-DUNK',   'Nike Dunk Low Retro White Black',  11,'Nike','Leather upper, padded collar, rubber cupsole',110.00,48.00,0.420,TRUE,180,18,3),
('FW-ADI-GAZELLE','Adidas Gazelle Indoor Shoes',       11,'Adidas','Suede upper, rubber sole, shell toe, vintage design',90.00,39.00,0.420,TRUE,210,22,4),
-- KITCHEN APPLIANCES (category_id=12) ~15 products
('KA-DYS-V15AB',  'Dyson V15 Detect Absolute Vacuum', 12,'Dyson','Laser dust detection, HEPA filter, 60-min runtime',749.99,450.00,3.100,TRUE,80,8,17),
('KA-DYS-AM09FH', 'Dyson Pure Hot+Cool Fan Purifier', 12,'Dyson','HEPA+Carbon filter, heat & cool, 350° oscillation',549.99,330.00,2.800,TRUE,60,6,17),
('KA-PHI-EP5365', 'Philips Espresso Machine EP5365',  12,'Philips','LatteGo milk system, 12 drinks, ceramic grinder',699.99,415.00,8.200,TRUE,45,5,8),
('KA-BOC-TASSIM', 'Bosch Tassimo My Way 2 Coffee',    12,'Bosch','Multi-drink, Intellibrew technology, 1400W',79.99,35.00,2.600,TRUE,120,15,10),
('KA-PHI-AHD9280','Philips 3000 Series Air Fryer',    12,'Philips','7L XL capacity, Rapid Air, digital touchscreen',149.99,68.00,4.500,TRUE,150,18,8),
('KA-BOC-MUMSM3', 'Bosch Serie 4 Stand Mixer MUM5',   12,'Bosch','900W motor, 3.9L stainless bowl, 7 speeds',329.99,185.00,6.800,TRUE,55,6,10),
('KA-PHI-HR3655', 'Philips Blender HR3655 Pro',        12,'Philips','Titanium blades, 1.8L Tritan jar, 1400W',129.99,58.00,2.100,TRUE,90,10,8),
('KA-DYS-AM10PHR','Dyson Purifier Cool TP09 Tower',   12,'Dyson','HEPA 13 & activated carbon, 350° oscillation',549.99,330.00,4.700,TRUE,40,5,17),
('KA-BOC-SMPHEX', 'Bosch SmartMix Hand Mixer',        12,'Bosch','500W, 5 speeds + turbo, bowl rest, soft grip',49.99,22.00,0.890,TRUE,180,20,10),
('KA-PHI-HD9867', 'Philips Airfryer XXL Premium',     12,'Philips','7L, Smart Sensing tech, Fat Removal technology',279.99,126.00,5.900,TRUE,70,8,8),
-- FURNITURE (category_id=13) ~10 products
('FU-IKE-KALLAX', 'IKEA KALLAX Shelf Unit 4x4',       13,'IKEA','Versatile shelving, 147x147cm, white finish',279.99,110.00,67.000,TRUE,30,4,16),
('FU-IKE-MALM4D', 'IKEA MALM 4-Drawer Chest',         13,'IKEA','High gloss white, 80x100cm, easy assembly',249.99,98.00,44.000,TRUE,25,3,16),
('FU-IKE-FRIHTN', 'IKEA FRIHETEN Corner Sofa-Bed',    13,'IKEA','Storage compartment, 151x230x66cm, Skiftebo dark grey',699.99,275.00,88.000,TRUE,15,2,16),
('FU-IKE-HEMNES', 'IKEA HEMNES Bookcase 3-Shelf',     13,'IKEA','Solid pine, 90x197cm, light brown stain',149.99,58.00,32.000,TRUE,35,4,16),
-- FITNESS EQUIPMENT (category_id=14) ~10 products
('FE-UAR-MATPRO', 'Under Armour Yoga Mat Pro 5mm',    14,'Under Armour','Non-slip surface, 183x61cm, carrying strap',45.00,19.00,1.350,TRUE,200,25,20),
('FE-ADI-RBAND',  'Adidas Resistance Band Set 5-Pack',14,'Adidas','Light to X-Heavy resistance, latex free, fabric',35.00,14.00,0.380,TRUE,300,35,4),
('FE-NIK-BBPUMP', 'Nike Premium Basketball',          14,'Nike','Regulation size 7, deep channel design, indoor/outdoor',35.00,15.00,0.620,TRUE,250,30,3),
('FE-UAR-HGGLOVES','Under Armour UA F8 Football Gloves',14,'Under Armour','GlueGrip palm, moisture transport, stretch knit back',30.00,13.00,0.120,TRUE,180,20,20),
-- OUTDOOR GEAR (category_id=15) ~10 products
('OG-COL-TENTEX', 'Coleman Sundome 4-Person Tent',    15,'Coleman','Easy setup, WeatherTec system, 9x7ft',149.99,67.00,5.900,TRUE,80,10,13),
('OG-COL-SLPBG',  'Coleman Brazos Cold Weather Bag',  15,'Coleman','20°F rating, comfort cuff, Thermolock draft tube',69.99,31.00,2.100,TRUE,100,12,13),
('OG-COL-COOLER', 'Coleman 54-Quart Steel Belted Cooler',15,'Coleman','5-day ice retention, bottle opener, drain plug',129.99,58.00,9.500,TRUE,60,8,13),
('OG-COL-CAMPST', 'Coleman Classic Propane Camp Stove',15,'Coleman','2 burner, 20,000 BTU, WindBlock panels, matchless ignition',69.99,31.00,2.600,TRUE,75,10,13),
-- BEAUTY (category_id=5) ~15 products
('BT-LOR-ELVSERUM','L''Oreal Paris Elvive Serum 200ml',5,'L''Oreal','Extraordinary Oil Serum, all hair types, anti-frizz',14.99,5.50,0.250,TRUE,400,50,14),
('BT-LOR-REVITAL','L''Oreal Revitalift Filler Serum 30ml',5,'L''Oreal','1.5% pure hyaluronic acid, replumping, anti-wrinkle',34.99,13.00,0.120,TRUE,350,45,14),
('BT-LOR-INFAL',   'L''Oreal Infallible 24H Foundation',5,'L''Oreal','24H wear, SPF25, 35 shades, matte finish',19.99,7.50,0.140,TRUE,500,60,14),
('BT-LOR-VOLUMINM','L''Oreal Paris Voluminous Mascara',5,'L''Oreal','5X volume, no clumping, washable black',11.99,4.20,0.090,TRUE,600,70,14),
('BT-LOR-ELIXTX',  'L''Oreal Extraordinary Oil Treatment',5,'L''Oreal','Lightweight, 6 rare oils, instant shine',12.99,4.80,0.100,TRUE,450,55,14),
('BT-UNI-SHEA',    'Unilever Dove Shea Butter Body Lotion 400ml',5,'Dove','48h moisturising, shea butter & vanilla',8.99,3.20,0.450,TRUE,700,80,9),
('BT-UNI-DOVE7BAR','Dove Original Beauty Cream Bar 7-Pack',5,'Dove','Moisturising cream, 1/4 moisturising lotion formula',12.99,4.50,0.630,TRUE,800,90,9),
('BT-UNI-AXEDEO',  'Axe Dark Temptation Deo Bodyspray 150ml',5,'Axe','48h odour protection, dark chocolate scent',6.99,2.50,0.160,TRUE,650,75,9),
('BT-UNI-SIMPL',   'Simple Kind to Skin Moisturiser SPF15 125ml',5,'Simple','No perfume, colour or harsh chemicals, SPF15',9.99,3.60,0.140,TRUE,500,60,9),
('BT-LOR-MICEL',   'L''Oreal Paris Micellar Water 400ml',5,'L''Oreal','3-in-1 cleanser, toner, makeup remover',12.99,4.80,0.440,TRUE,450,55,14),
-- Additional TELEVISIONS
('TV-SAM-43Q60',  'Samsung 43" QLED 4K Smart TV Q60B',     6,'Samsung','QLED 4K, Quantum Processor Lite 4K, Smart Hub',499.99,295.00,8.100,TRUE,80,8,2),
('TV-LG-43UQ91',  'LG 43" UHD 4K Smart TV UQ9100',        6,'LG','4K UHD, α5 AI Processor, HDR10, WebOS 22',379.99,222.00,7.600,TRUE,90,10,12),
('TV-SON-43X75',  'Sony 43" BRAVIA X75WL 4K Smart TV',    6,'Sony','X-Reality PRO, Motionflow XR, Android TV',449.99,265.00,8.400,TRUE,75,8,6),
-- Additional SMARTPHONES
('PH-SAM-A15',   'Samsung Galaxy A15 5G 128GB',            7,'Samsung','MediaTek Dimensity 6100+, 50MP camera, 5000mAh',249.99,142.00,0.199,TRUE,280,30,2),
('PH-APL-IP13',  'Apple iPhone 13 128GB',                  7,'Apple','A15 Bionic, Dual 12MP cameras, Super Retina XDR',599.99,352.00,0.174,TRUE,80,10,5),
('PH-SAM-S23FE', 'Samsung Galaxy S23 FE 128GB',            7,'Samsung','Snapdragon 8 Gen 1, 50MP OIS camera, 4500mAh',499.99,293.00,0.209,TRUE,120,15,2),
-- Additional LAPTOPS
('LT-SAM-GBP14', 'Samsung Galaxy Book3 Pro 14"',           8,'Samsung','Intel Core i5-1340P, 16GB, 512GB, 2.8K AMOLED',1149.99,678.00,1.170,TRUE,40,5,2),
('LT-SON-FLP16', 'Sony VAIO F16 16" Laptop',               8,'Sony','Intel Core i7-13700H, 16GB, 512GB SSD, IPS',1199.99,708.00,1.990,TRUE,22,3,6),
-- Additional MEN'S APPAREL
('MA-NIK-WINDFL','Nike Windrunner Jacket Men''s',           9,'Nike','Water-repellent, packable, iconic chevron design',120.00,52.00,0.390,TRUE,160,18,3),
('MA-ADI-STHLTE','Adidas Stadium Fleece Zip Hoodie',        9,'Adidas','Full zip, kangaroo pocket, ribbed hem and cuffs',75.00,33.00,0.610,TRUE,190,22,4),
('MA-UAR-PROJECKT','Under Armour Project Rock Polo',        9,'Under Armour','UA ArmourDry fabric, split-hem, UPF 30+',70.00,31.00,0.260,TRUE,170,20,20),
('MA-NIK-CLUBPOLO','Nike Sportswear Club Polo Shirt',       9,'Nike','Pique fabric, ribbed collar, flat knit cuffs',60.00,26.00,0.250,TRUE,200,22,3),
('MA-ADI-CLIMWARM','Adidas Climawarm Full Zip Hoodie',      9,'Adidas','Climawarm material, kangaroo pocket, slim fit',85.00,37.00,0.560,TRUE,150,18,4),
('MA-RBK-IDENTT', 'Reebok Identity Fleece Jogger',          9,'Reebok','Tapered fit, cuffed hem, elastic waistband',50.00,22.00,0.380,TRUE,210,25,15),
('MA-NIK-PROBASKT','Nike Pro Basketball Compression Shorts', 9,'Nike','7" inseam, Dri-FIT technology, hip pockets',40.00,17.00,0.190,TRUE,260,30,3),
('MA-ADI-TABELA','Adidas Tabela 23 Football Jersey',        9,'Adidas','AEROREADY moisture management, recycled polyester',25.00,10.00,0.160,TRUE,350,40,4),
('MA-UAR-SPORTSTYLE','Under Armour Sportstyle Graphic Tee', 9,'Under Armour','Cotton-blend, loose fit, screen print graphic',30.00,13.00,0.200,TRUE,300,35,20),
-- Additional WOMEN'S APPAREL
('WA-NIK-SPORTSWBRA','Nike Sportswear Medium Support Bra',  10,'Nike','Dri-FIT, removable pads, adjustable straps',45.00,19.00,0.120,TRUE,260,30,3),
('WA-ADI-ALLYGA','Adidas All Me Yoga Sports Bra',           10,'Adidas','Medium support, moisture-absorbing, removable pads',40.00,17.00,0.110,TRUE,240,28,4),
('WA-HM-OVSIZE',  'H&M Oversized Knit Sweater',             10,'H&M','Dropped shoulders, ribbed trims, cosy fit',39.99,15.00,0.480,TRUE,200,22,7),
('WA-ZAR-WIDELEG','Zara Wide Leg High Waist Trousers',      10,'Zara','Pleated front, wide leg, belt loops',49.99,19.00,0.420,TRUE,170,20,11),
('WA-NIK-WINDFL2','Nike Windrunner Jacket Women''s',         10,'Nike','Water-repellent, packable, chevron design, slim fit',120.00,52.00,0.360,TRUE,150,18,3),
('WA-ADI-PARKAHD','Adidas Helionic Down Jacket',            10,'Adidas','550 fill power down, water-repellent, packs into pocket',249.99,113.00,0.540,TRUE,90,10,4),
('WA-RBK-CLASSV', 'Reebok Classic Varsity Jacket',          10,'Reebok','Satin shell, embroidered patches, snap buttons',119.99,54.00,0.820,TRUE,80,10,15),
('WA-UAR-MERIDN', 'Under Armour Meridian Leggings',         10,'Under Armour','Ultra-soft, moisture-wicking, side pockets, squat-proof',75.00,33.00,0.270,TRUE,220,25,20),
('WA-NIK-ESSNTAL','Nike Essentials Fleece Pullover Hoodie', 10,'Nike','Standard fit, Dri-FIT fleece, front kangaroo pocket',65.00,28.00,0.480,TRUE,200,22,3),
('WA-HM-LINPANTS','H&M Linen-Blend Pull-On Trousers',       10,'H&M','Relaxed fit, elasticated waist, side seam pockets',34.99,13.00,0.310,TRUE,220,25,7),
-- Additional FOOTWEAR
('FW-NIK-REAX11', 'Nike Reax 11 Training Shoe Men''s',      11,'Nike','Multi-directional traction, foam midsole, mesh',75.00,33.00,0.440,TRUE,190,20,3),
('FW-ADI-TERREX', 'Adidas Terrex Swift R3 GTX Hiking',      11,'Adidas','GORE-TEX, Continental rubber outsole, lightweight',160.00,73.00,0.510,TRUE,100,12,4),
('FW-NB-530',     'New Balance 530 Retro Running Shoe',     11,'New Balance','ABZORB midsole, mesh and suede upper, N logo',95.00,42.00,0.430,TRUE,180,20,18),
('FW-RBK-NANO12', 'Reebok Nano X3 Training Shoe',           11,'Reebok','Floatride Energy Foam, wide toe box, flexfilm',130.00,57.00,0.470,TRUE,140,15,15),
('FW-UAR-CHARGEDRS','Under Armour Charged Assert 10 Men''s',11,'Under Armour','Charged cushioning, knit upper, offset 8mm',65.00,28.00,0.390,TRUE,200,22,20),
('FW-NIK-METCON9','Nike Metcon 9 Training Shoe',            11,'Nike','Stable base, React foam, wider toe box',130.00,57.00,0.510,TRUE,130,15,3),
('FW-ADI-RUNFALC','Adidas Runfalcon 3.0 Running Shoe',      11,'Adidas','Cloudfoam midsole, mesh upper, TPU heel cap',55.00,24.00,0.350,TRUE,250,28,4),
('FW-NB-574',     'New Balance 574 Core Sneaker',           11,'New Balance','ENCAP midsole, suede and mesh upper, classic design',80.00,35.00,0.440,TRUE,200,22,18),
-- Additional KITCHEN APPLIANCES
('KA-PHI-GC4564', 'Philips 3000 Series Grillmaster Grill', 12,'Philips','Floating plates, fat drainage, 2000W, non-stick',89.99,40.00,1.900,TRUE,100,12,8),
('KA-BOC-BLDR',   'Bosch BlenderJar CleverMixx Blender',   12,'Bosch','800W, 1.5L, stainless steel blades, ice crush',49.99,22.00,1.400,TRUE,150,18,10),
('KA-DYS-WUP1',   'Dyson WashG1 Wet & Dry Vacuum',         12,'Dyson','Simultaneous washing and drying, HEPA filter',599.99,360.00,4.200,TRUE,35,4,17),
('KA-PHI-HD9252',  'Philips Airfryer Compact 4.1L',         12,'Philips','4.1L, Rapid Air technology, 90% less fat',99.99,45.00,3.100,TRUE,170,20,8),
('KA-BOC-KETL',    'Bosch Styline Collection Kettle',       12,'Bosch','1.7L, 3000W, stainless steel, keep warm 40min',59.99,26.00,1.100,TRUE,140,16,10),
-- Additional FURNITURE
('FU-IKE-ALEX',   'IKEA ALEX Drawer Unit on Castors',       13,'IKEA','6 drawers, white, 36x116cm, locks on castors',149.99,58.00,28.000,TRUE,40,5,16),
('FU-IKE-LACK',   'IKEA LACK Side Table 55x55cm',           13,'IKEA','Black-brown finish, 55x55x45cm, easy assembly',14.99,5.00,3.800,TRUE,120,15,16),
('FU-IKE-POANG',  'IKEA POANG Armchair',                    13,'IKEA','Birch veneer frame, Skiftebo yellow cushion',239.99,94.00,18.000,TRUE,30,4,16),
('FU-IKE-BRIMNES','IKEA BRIMNES Wardrobe with Doors',       13,'IKEA','Adjustable hinges, 117x190cm, white',299.99,118.00,54.000,TRUE,18,2,16),
-- Additional FITNESS EQUIPMENT
('FE-NIK-SWIMMGL','Nike Swim Lap Goggles',                  14,'Nike','Silicone gasket, UV protection, anti-fog lens',20.00,8.00,0.080,TRUE,350,40,3),
('FE-ADI-YOMATT',  'Adidas Premium Yoga Mat 5mm',           14,'Adidas','Non-slip TPE, 173x61cm, alignment lines, carrier',45.00,19.00,1.350,TRUE,220,25,4),
('FE-UAR-WEIGHTVST','Under Armour Weighted Training Vest 9kg',14,'Under Armour','Adjustable weights, ventilated, reflective',149.99,67.00,9.800,TRUE,50,6,20),
('FE-NIK-SPEEDROPE','Nike Speed Jump Rope',                  14,'Nike','Aluminium handles, weighted 90g heads, 3m cable',25.00,10.00,0.320,TRUE,300,35,3),
('FE-ADI-FOAMRLL', 'Adidas Foam Roller 45cm',               14,'Adidas','EVA foam, high-density, grid texture, 45x15cm',30.00,12.00,0.380,TRUE,250,30,4),
-- Additional OUTDOOR GEAR
('OG-COL-BACKPK',  'Coleman Hooligan 40L Backpack',         15,'Coleman','Rain cover, sternum strap, multiple compartments',79.99,35.00,1.100,TRUE,90,10,13),
('OG-COL-HEADLMP', 'Coleman MicroPacker Compact Headlamp',  15,'Coleman','175 lumens, 3 modes, IPX4 water resistant',24.99,11.00,0.087,TRUE,200,25,13),
('OG-COL-TARPW',   'Coleman Waterproof Heavy-Duty Tarp',    15,'Coleman','12x10ft, 150D polyester, welded D-rings',39.99,18.00,1.600,TRUE,120,15,13),
-- Extra ELECTRONICS accessories (category_id=7/8 accessories, using cat 7)
('ACC-APL-AIRPD3', 'Apple AirPods 3rd Generation',          7,'Apple','Adaptive EQ, Spatial Audio, IPX4, Lightning case',169.99,98.00,0.040,TRUE,300,30,5),
('ACC-APL-AIRPDPRO','Apple AirPods Pro 2nd Generation',     7,'Apple','Active Noise Cancellation, Transparency, H2 chip',249.99,145.00,0.061,TRUE,250,25,5),
('ACC-SAM-BUDS2',  'Samsung Galaxy Buds2 Pro',              7,'Samsung','Active Noise Cancellation, 360 audio, IPX7',229.99,133.00,0.061,TRUE,220,22,2),
('ACC-SON-WH1000', 'Sony WH-1000XM5 Wireless Headphones',  7,'Sony','Industry-leading ANC, 30h battery, multipoint',349.99,202.00,0.250,TRUE,180,18,6),
('ACC-APL-WATCH9', 'Apple Watch Series 9 GPS 45mm',         7,'Apple','S9 chip, Double Tap, Crash Detection, Always-On',429.99,249.00,0.039,TRUE,200,20,5),
('ACC-SAM-WATCH6', 'Samsung Galaxy Watch6 Classic 47mm',    7,'Samsung','Rotating bezel, BioActive sensor, sapphire glass',399.99,232.00,0.059,TRUE,150,15,2),
('ACC-APL-CHARGER','Apple MagSafe Charger 1m',              8,'Apple','15W MagSafe, USB-C, iPhone 12/13/14/15 compatible',39.99,15.00,0.072,TRUE,500,50,5),
('ACC-SAM-CHARGER','Samsung 45W Super Fast Charger',        8,'Samsung','USB-C, AFC/PD3.0, for Galaxy S21/S22/S23/S24',34.99,13.00,0.063,TRUE,450,50,2),
('ACC-SON-SPKR',   'Sony SRS-XB33 Portable Bluetooth Speaker',8,'Sony','Extra Bass, IP67, 24h battery, Party Connect',129.99,75.00,0.730,TRUE,220,22,6),
('ACC-APL-IPAD11', 'Apple iPad 10th Gen 10.9" 64GB Wi-Fi', 8,'Apple','A14 Bionic, 10.9" Liquid Retina, USB-C, 5G ready',449.99,263.00,0.477,TRUE,140,15,5),
('ACC-SAM-TABS9',  'Samsung Galaxy Tab S9 FE Wi-Fi 128GB', 8,'Samsung','Exynos 1380, 10.9" TFT LCD, IP68, S Pen included',449.99,263.00,0.523,TRUE,110,12,2),
-- Extra BEAUTY products
('BT-LOR-GLOSSY',  'L''Oreal Paris Colour Riche Gloss',     5,'L''Oreal','Shine gloss, 48 shades, conditioning formula',10.99,3.90,0.060,TRUE,550,65,14),
('BT-UNI-SUNSCRN', 'Dove Men+Care Body Wash 400ml',         5,'Dove','Hydra Boost technology, deep clean formula',8.99,3.20,0.430,TRUE,680,78,9),
('BT-LOR-PRFUM',   'L''Oreal Paris La Vie Est Belle EDP 50ml',5,'L''Oreal','Floral gourmand, iris, praline, vanilla, 50ml',64.99,24.00,0.220,TRUE,200,25,14),
('BT-UNI-TREESE',  'TRESemmé Pro Pure Shampoo 740ml',       5,'TRESemmé','Sulfate-free, paraben-free, vegan formula',9.99,3.60,0.760,TRUE,500,60,9),
('BT-LOR-ELNTWST', 'L''Oreal Elnett Hairspray 400ml',       5,'L''Oreal','Normal hold, unscented, fine mist spray',8.99,3.20,0.300,TRUE,600,70,9),
-- Additional TELEVISIONS (complete set)
('TV-SAM-32T4302','Samsung 32" HD Smart TV T4302',          6,'Samsung','HD Ready, PurColor, Smart TV, Apple AirPlay',249.99,145.00,4.600,TRUE,100,12,2),
('TV-LG-55UR87',  'LG 55" UHD 4K Smart TV UR8750',         6,'LG','α5 Gen6 AI Processor, FILMMAKER MODE, HDR10',549.99,322.00,13.200,TRUE,60,8,12),
('TV-SON-55X80',  'Sony 55" BRAVIA X80L 4K Smart TV',      6,'Sony','X1 4K HDR processor, XR 4K Upscaling, Google TV',699.99,412.00,15.800,TRUE,55,7,6),
-- Additional SMARTPHONES
('PH-SAM-A25',    'Samsung Galaxy A25 5G 128GB',            7,'Samsung','Exynos 1280, 50MP OIS, 5000mAh, Super AMOLED',299.99,172.00,0.197,TRUE,260,28,2),
('PH-APL-IPSE2',  'Apple iPhone SE 2nd Gen 64GB',           7,'Apple','A13 Bionic, Touch ID, 4.7" Retina HD, Portrait mode',329.99,193.00,0.148,TRUE,50,6,5),
-- Additional LAPTOPS
('LT-APL-MACMINI','Apple Mac Mini M2 Pro 512GB',            8,'Apple','M2 Pro chip, 16GB RAM, 512GB SSD, Thunderbolt 4',1299.99,763.00,1.180,TRUE,35,4,5),
('LT-SAM-GBE13',  'Samsung Galaxy Book3 Edge 13.3"',        8,'Samsung','Snapdragon X Elite, 16GB, 512GB, AMOLED',1449.99,853.00,1.170,TRUE,25,3,2),
-- Additional FOOTWEAR
('FW-NIK-BLAZERM','Nike Blazer Mid 77 Vintage Men''s',      11,'Nike','Full-grain leather upper, padded collar, rubber sole',105.00,46.00,0.450,TRUE,175,18,3),
('FW-ADI-FORUM84','Adidas Forum 84 High Shoes',             11,'Adidas','Full-grain leather, ankle strap, rubber cupsole',110.00,48.00,0.500,TRUE,155,16,4),
('FW-NB-2002R',   'New Balance 2002R Trail Running Shoe',   11,'New Balance','SBS rubber outsole, N-ergy midsole, nubuck leather',130.00,57.00,0.430,TRUE,110,12,18),
('FW-RBK-CLASSIC','Reebok Classic Leather Legacy Shoes',    11,'Reebok','Full-grain leather upper, EVA sockliner, rubber',90.00,39.00,0.390,TRUE,195,20,15),
('FW-UAR-MICRO2', 'Under Armour Micro G Pursuit BP Running',11,'Under Armour','Micro G foam, mesh upper, 3-color sole',80.00,35.00,0.380,TRUE,170,18,20),
-- Additional KITCHEN APPLIANCES
('KA-PHI-TOASTR', 'Philips HD2590 Toaster 4-slice',         12,'Philips','4-slice, 8 settings, defrost/reheat/cancel, 1800W',49.99,22.00,1.300,TRUE,160,18,8),
('KA-BOC-HANDBLND','Bosch ErgoMixx Hand Blender 600W',      12,'Bosch','600W, 12 speeds, stainless steel shaft, splash-free',49.99,22.00,0.610,TRUE,170,20,10),
('KA-DYS-PURECOOL','Dyson Pure Cool DP04 Purifier Fan',     12,'Dyson','360° Glass HEPA filter, OLED display, 10 speeds',449.99,270.00,3.780,TRUE,45,5,17),
('KA-PHI-WAFLM',  'Philips Viva Collection Waffle Maker',   12,'Philips','900W, non-stick plates, ready indicator light',49.99,22.00,1.350,TRUE,140,15,8),
-- Additional FITNESS EQUIPMENT
('FE-UAR-STEPUP',  'Under Armour Training Step Platform',   14,'Under Armour','Non-slip surface, 4 adjustable risers, 90kg limit',65.00,29.00,3.200,TRUE,80,10,20),
('FE-NIK-AGILITY', 'Nike Sport Speed Rope',                 14,'Nike','Tangle-free bearings, foam handles, adjustable 9.5ft',20.00,8.00,0.260,TRUE,320,38,3),
('FE-ADI-PULLUP',  'Adidas Power Band Pull-Up Assist',      14,'Adidas','Heavy resistance, natural latex, 208cm loop',18.00,7.00,0.180,TRUE,350,42,4),
-- Additional OUTDOOR GEAR
('OG-COL-LNTRN',   'Coleman 800L LED Lantern',              15,'Coleman','800 lumens, 75h runtime, D-cell, IPX4',44.99,20.00,0.680,TRUE,160,18,13),
('OG-COL-GRILLL',  'Coleman RoadTrip 285 Portable Grill',   15,'Coleman','285 sq-in cooking surface, push-button ignition, 20,000 BTU',149.99,67.00,7.900,TRUE,55,7,13),
-- Additional BEAUTY
('BT-LOR-EYELINR', 'L''Oreal Paris Infallible Grip Liner',  5,'L''Oreal','36H wear, micro-precision tip, 20 shades',10.99,3.90,0.030,TRUE,580,68,14),
('BT-UNI-CNDTNR',  'Dove Intense Repair Conditioner 700ml', 5,'Dove','Keratin actives, for damaged hair, deep repair',9.99,3.60,0.720,TRUE,500,60,9),
('BT-LOR-BRONZR',  'L''Oreal Paris True Match Bronzer',     5,'L''Oreal','4-shade bronzer palette, buildable coverage, matte',16.99,6.10,0.100,TRUE,420,50,14),
('BT-UNI-NTRSRC',  'Toni & Guy Nourish Reconstruction Mask', 5,'Toni & Guy','250ml, bonds protein, for damaged hair',11.99,4.30,0.270,TRUE,380,45,9),
-- Additional MEN'S APPAREL
('MA-NIK-PROSHIRT','Nike Pro Dri-FIT Long Sleeve Top',       9,'Nike','Base layer, tight fit, 4-way stretch, flatlock seams',55.00,24.00,0.220,TRUE,240,28,3),
('MA-ADI-BLKJKT',  'Adidas Tiro 23 Competition Jacket',     9,'Adidas','AEROREADY, 100% recycled polyester, zip pockets',70.00,31.00,0.340,TRUE,195,22,4),
('MA-UAR-VENT',    'Under Armour Vent Woven 1/2 Zip Top',    9,'Under Armour','UA Storm technology, half-zip, mesh panels',65.00,29.00,0.260,TRUE,210,24,20),
-- Additional WOMEN'S APPAREL
('WA-NIK-ICONCLSH','Nike Icon Clash Skirt',                  10,'Nike','Dri-FIT, inner shorts, 15" length, side pockets',50.00,22.00,0.200,TRUE,190,22,3),
('WA-ADI-ORIGNAK', 'Adidas Originals Adicolor Jacket',       10,'Adidas','Woven fabric, patch pocket, relaxed fit',90.00,39.00,0.430,TRUE,155,18,4),
('WA-HM-CHKBLZ',   'H&M Checked Tailored Blazer',           10,'H&M','Regular fit, checked pattern, notched lapels',59.99,23.00,0.520,TRUE,140,16,7),
-- Additional LAPTOPS (complete 200)
('ACC-APL-APPLETV', 'Apple TV 4K 3rd Gen Wi-Fi + Ethernet', 8,'Apple','A15 Bionic, HDR10+, Dolby Vision, Thread router',129.99,75.00,0.272,TRUE,220,22,5),
('ACC-SAM-GALAXY',  'Samsung 27" Smart Monitor M8 4K',      8,'Samsung','4K, 60Hz, Tizen OS, built-in TV apps, 3ms',699.99,412.00,5.400,TRUE,75,8,2),
('ACC-SON-PS5CTL',  'Sony DualSense Wireless Controller',   8,'Sony','Haptic feedback, adaptive triggers, USB-C, white',69.99,38.00,0.280,TRUE,300,30,6),
('ACC-SAM-TBAND7',  'Samsung Galaxy Fit3 Fitness Band',     7,'Samsung','1.6" AMOLED, 13 workout modes, 13 day battery, IP68',49.99,27.00,0.026,TRUE,350,35,2);
-- end products

-- =============================================================================
-- SEED DATA: CUSTOMERS (2000 rows)
-- Using generate_series for bulk generation with realistic variation
-- DQ ISSUE 1: 50 customers with NULL email (customer_id 151–200)
-- DQ ISSUE 5: 3 customers with future created_at dates (customer_id 1998, 1999, 2000)
-- =============================================================================
INSERT INTO customers (
  customer_code, first_name, last_name, email, phone, date_of_birth,
  gender, address, city, state_province, country_id, zip_code,
  loyalty_tier, loyalty_points, is_active, acquired_channel, created_at, updated_at
)
SELECT
  'CUST-' || LPAD(n::TEXT, 6, '0') AS customer_code,
  (ARRAY['James','John','Robert','Michael','William','David','Joseph','Thomas','Charles','Christopher',
         'Daniel','Matthew','Anthony','Mark','Donald','Steven','Paul','Andrew','Joshua','Kenneth',
         'Emma','Olivia','Ava','Isabella','Sophia','Mia','Charlotte','Amelia','Harper','Evelyn',
         'Abigail','Emily','Elizabeth','Mila','Ella','Avery','Sofia','Camila','Aria','Scarlett',
         'Victoria','Madison','Luna','Grace','Chloe','Penelope','Layla','Riley','Zoey','Nora'])[((n-1) % 50) + 1] AS first_name,
  (ARRAY['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Martinez','Wilson',
         'Anderson','Taylor','Thomas','Hernandez','Moore','Martin','Jackson','Thompson','White','Lopez',
         'Lee','Gonzalez','Harris','Clark','Lewis','Robinson','Walker','Perez','Hall','Young',
         'Allen','Sanchez','Wright','King','Scott','Green','Baker','Adams','Nelson','Carter',
         'Mitchell','Perez','Roberts','Turner','Phillips','Campbell','Parker','Evans','Edwards','Collins'])[((n-1) % 50) + 1] AS last_name,
  CASE
    -- DQ ISSUE 1: customers 151-200 have NULL email
    WHEN n BETWEEN 151 AND 200 THEN NULL
    ELSE LOWER(
      (ARRAY['james','john','robert','michael','william','david','joseph','thomas','charles','christopher',
             'daniel','matthew','anthony','mark','donald','steven','paul','andrew','joshua','kenneth',
             'emma','olivia','ava','isabella','sophia','mia','charlotte','amelia','harper','evelyn',
             'abigail','emily','elizabeth','mila','ella','avery','sofia','camila','aria','scarlett',
             'victoria','madison','luna','grace','chloe','penelope','layla','riley','zoey','nora'])[((n-1) % 50) + 1]
    ) || '.' ||
    LOWER(
      (ARRAY['smith','johnson','williams','brown','jones','garcia','miller','davis','martinez','wilson',
             'anderson','taylor','thomas','hernandez','moore','martin','jackson','thompson','white','lopez',
             'lee','gonzalez','harris','clark','lewis','robinson','walker','perez','hall','young',
             'allen','sanchez','wright','king','scott','green','baker','adams','nelson','carter',
             'mitchell','perez','roberts','turner','phillips','campbell','parker','evans','edwards','collins'])[((n-1) % 50) + 1]
    ) || n || '@' ||
    (ARRAY['gmail.com','yahoo.com','hotmail.com','outlook.com','icloud.com','protonmail.com'])[((n-1) % 6) + 1]
  END AS email,
  '+1-' || (200 + (n % 800))::TEXT || '-555-' || LPAD((1000 + n % 9000)::TEXT, 4, '0') AS phone,
  (DATE '1960-01-01' + (n * 127 % 16000) * INTERVAL '1 day')::DATE AS date_of_birth,
  (ARRAY['M','F','M','F','M','F','M','F','M','F','M','F','M','F','M','F','M','F','M','F',
         'M','F','Other','M','F','M','F','M','F','M','M','F','M','F','M','F','M','F','M','F',
         'M','F','M','F','M','F','M','F','Unknown','M'])[((n-1) % 50) + 1] AS gender,
  n::TEXT || ' ' ||
  (ARRAY['Main St','Oak Ave','Maple Dr','Cedar Ln','Pine Rd','Elm St','Park Blvd','Lake Dr',
         'Hill Rd','River Rd','Sunset Blvd','Broadway','Madison Ave','Lexington Ave','5th Ave'])[((n-1) % 15) + 1] AS address,
  (ARRAY['New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia','San Antonio','San Diego',
         'Dallas','San Jose','Austin','Jacksonville','Fort Worth','Columbus','Indianapolis',
         'Toronto','Vancouver','Montreal','Calgary','Ottawa',
         'London','Manchester','Birmingham','Edinburgh','Bristol',
         'Sydney','Melbourne','Brisbane','Perth','Adelaide'])[((n-1) % 30) + 1] AS city,
  (ARRAY['New York','California','Illinois','Texas','Arizona','Pennsylvania','Texas','California',
         'Texas','California','Texas','Florida','Texas','Ohio','Indiana',
         'Ontario','British Columbia','Quebec','Alberta','Ontario',
         'England','England','England','Scotland','England',
         'New South Wales','Victoria','Queensland','Western Australia','South Australia'])[((n-1) % 30) + 1] AS state_province,
  (ARRAY['US','US','US','US','US','US','US','US','US','US','US','US','US','US','US',
         'CA','CA','CA','CA','CA',
         'GB','GB','GB','GB','GB',
         'AU','AU','AU','AU','AU'])[((n-1) % 30) + 1] AS country_id,
  LPAD((10000 + n * 31 % 89999)::TEXT, 5, '0') AS zip_code,
  (ARRAY['Bronze','Bronze','Bronze','Bronze','Silver','Silver','Silver','Gold','Gold','Platinum'])[((n * 7) % 10) + 1] AS loyalty_tier,
  (n * 137 % 15000) AS loyalty_points,
  CASE WHEN n % 50 = 0 THEN FALSE ELSE TRUE END AS is_active,
  (ARRAY['organic','paid_search','social','referral','email','in_store','organic','paid_search','social','referral'])[((n-1) % 10) + 1] AS acquired_channel,
  -- DQ ISSUE 5: 3 customers with future created_at
  CASE
    WHEN n IN (1998, 1999, 2000) THEN NOW() + (n - 1997) * INTERVAL '30 days'
    ELSE TIMESTAMP '2021-01-01' + ((n * 293) % 1095) * INTERVAL '1 day'
  END AS created_at,
  TIMESTAMP '2021-01-01' + ((n * 293) % 1095) * INTERVAL '1 day' AS updated_at
FROM generate_series(1, 2000) AS n;

-- =============================================================================
-- SEED DATA: PROMOTIONS (30 rows)
-- =============================================================================
INSERT INTO promotions (promo_code, description, discount_type, discount_value, min_order_amount, start_date, end_date, usage_limit, times_used, is_active) VALUES
('WELCOME10',    'New customer welcome discount 10%',       'percentage',  10.00,  0.00,   '2022-01-01','2024-12-31',  NULL, 4821, TRUE),
('SUMMER20',     'Summer Sale 20% off everything',          'percentage',  20.00,  50.00,  '2022-06-01','2022-08-31',  5000, 4932, FALSE),
('FALL15',       'Fall season 15% discount',                'percentage',  15.00,  75.00,  '2022-09-01','2022-11-30',  3000, 2876, FALSE),
('XMAS2022',     'Christmas 2022 - $25 off $150+',         'fixed',       25.00,  150.00, '2022-12-01','2022-12-31',  10000,9234, FALSE),
('NEWYEAR23',    'New Year 2023 - 12% off',                'percentage',  12.00,  100.00, '2023-01-01','2023-01-15',  2000, 1876, FALSE),
('SPRING23',     'Spring refresh 18% off',                  'percentage',  18.00,  80.00,  '2023-03-20','2023-06-20',  4000, 3654, FALSE),
('SUMMER23',     'Summer 2023 - 25% off sports & outdoor',  'percentage',  25.00,  60.00,  '2023-06-01','2023-08-31',  5000, 4789, FALSE),
('BACKSCHOOL23', 'Back to School - 15% off electronics',    'percentage',  15.00,  200.00, '2023-08-01','2023-09-15',  3000, 2543, FALSE),
('FALL23',       'Fall 2023 - $30 off $200+',              'fixed',       30.00,  200.00, '2023-09-01','2023-11-30',  5000, 4321, FALSE),
('BF2023',       'Black Friday 30% off',                   'percentage',  30.00,  100.00, '2023-11-24','2023-11-27',  NULL, 18765,FALSE),
('CM2023',       'Cyber Monday extra 25% off',              'percentage',  25.00,  150.00, '2023-11-27','2023-11-27',  NULL, 12432,FALSE),
('XMAS2023',     'Christmas 2023 - $40 off $200+',         'fixed',       40.00,  200.00, '2023-12-01','2023-12-31',  10000,9876, FALSE),
('NEWYEAR24',    'New Year 2024 - 15% off sitewide',       'percentage',  15.00,  50.00,  '2024-01-01','2024-01-07',  5000, 4654, FALSE),
('FREESHIP',     'Free shipping on orders $75+',            'free_shipping',0.00,  75.00,  '2022-01-01','2024-12-31',  NULL, 32187,TRUE),
('BOGO50',       'Buy one get one 50% off clothing',        'bogo',        50.00,  0.00,   '2023-03-01','2023-04-30',  2000, 1876, FALSE),
('LOYALTY25',    'Loyalty Gold/Platinum members $25 off',   'fixed',       25.00,  100.00, '2022-01-01','2024-12-31',  NULL, 8432, TRUE),
('REFER20',      'Referral reward - 20% off',               'percentage',  20.00,  0.00,   '2022-01-01','2024-12-31',  NULL, 6543, TRUE),
('SPRING24',     'Spring 2024 - 20% off home & garden',    'percentage',  20.00,  100.00, '2024-03-20','2024-06-20',  4000, 3210, FALSE),
('SUMMER24',     'Summer 2024 - 22% off everything',       'percentage',  22.00,  80.00,  '2024-06-01','2024-08-31',  6000, 5432, TRUE),
('FLASH24',      'Flash sale - $15 off $100',              'fixed',       15.00,  100.00, '2024-02-14','2024-02-14',  500,  487,  FALSE),
('TECH10',       'Tech Tuesday 10% off electronics',        'percentage',  10.00,  300.00, '2024-01-01','2024-12-31',  NULL, 2341, TRUE),
('BEAUTY15',     'Beauty bonus 15% off beauty products',    'percentage',  15.00,  40.00,  '2024-04-01','2024-06-30',  3000, 2189, FALSE),
('SPORT20',      'Sport season 20% off sports equipment',   'percentage',  20.00,  60.00,  '2024-04-01','2024-07-31',  3000, 2654, FALSE),
('BF2024',       'Black Friday 2024 - 35% off',            'percentage',  35.00,  100.00, '2024-11-29','2024-12-02',  NULL, 0,    TRUE),
('CM2024',       'Cyber Monday 2024 - 28% off',            'percentage',  28.00,  150.00, '2024-12-02','2024-12-02',  NULL, 0,    TRUE),
('XMAS2024',     'Christmas 2024 - $50 off $300+',         'fixed',       50.00,  300.00, '2024-12-01','2024-12-31',  NULL, 0,    TRUE),
('EMPLOYEE15',   'Employee purchase program 15% off',       'percentage',  15.00,  0.00,   '2022-01-01','2024-12-31',  NULL, 3421, TRUE),
('VIP30',        'VIP Platinum member 30% off',             'percentage',  30.00,  200.00, '2022-01-01','2024-12-31',  NULL, 1234, TRUE),
('MOBILE10',     'Mobile app exclusive 10% off',            'percentage',  10.00,  50.00,  '2023-01-01','2024-12-31',  NULL, 9876, TRUE),
('BIRTHDAY20',   'Birthday month special 20% off',          'percentage',  20.00,  0.00,   '2022-01-01','2024-12-31',  NULL, 4567, TRUE);

-- =============================================================================
-- SEED DATA: ORDERS (5000 rows)
-- Realistic distribution: Q4 heavier, weekdays > weekends
-- DQ ISSUE 2: 20 duplicate order_codes (intentional)
-- DQ ISSUE 4: 5 orders with total_amount < subtotal (impossible without promotion)
-- =============================================================================
INSERT INTO orders (
  order_code, customer_id, store_id, order_date, status,
  payment_method, shipping_address, shipping_city, shipping_country_id,
  subtotal, discount_amount, shipping_cost, tax_amount, total_amount,
  currency_code, promo_code, created_at, updated_at
)
SELECT
  -- DQ ISSUE 2: orders 1-20 share codes with orders 21-40 (duplicate order_codes)
  CASE
    WHEN n <= 20 THEN 'ORD-DUP-' || LPAD(n::TEXT, 4, '0')
    WHEN n <= 40 THEN 'ORD-DUP-' || LPAD((n-20)::TEXT, 4, '0')  -- duplicates
    ELSE 'ORD-' || TO_CHAR(
      TIMESTAMP '2022-01-01' + ((n * 193) % 1095) * INTERVAL '1 day',
      'YYYYMMDD'
    ) || '-' || LPAD(n::TEXT, 5, '0')
  END AS order_code,
  -- customer_id: 1-2000
  (n % 2000) + 1 AS customer_id,
  -- store_id: weighted toward retail stores
  CASE
    WHEN n % 15 = 0 THEN 15   -- online US
    WHEN n % 20 = 0 THEN 20   -- online UK
    ELSE ((n * 7) % 28) + 1
  END AS store_id,
  -- order_date: 2022-01-01 to 2024-12-31, Q4 weighted (higher density Oct-Dec)
  CASE
    WHEN n % 4 = 0 THEN  -- Q4 heavy
      TIMESTAMP '2022-10-01' + ((n * 97) % 456) * INTERVAL '1 day'
                          + ((n * 13) % 86400) * INTERVAL '1 second'
    WHEN n % 4 = 1 THEN
      TIMESTAMP '2022-01-01' + ((n * 113) % 1095) * INTERVAL '1 day'
                          + ((n * 17) % 86400) * INTERVAL '1 second'
    WHEN n % 4 = 2 THEN
      TIMESTAMP '2023-01-01' + ((n * 131) % 730) * INTERVAL '1 day'
                          + ((n * 19) % 86400) * INTERVAL '1 second'
    ELSE
      TIMESTAMP '2024-01-01' + ((n * 151) % 366) * INTERVAL '1 day'
                          + ((n * 23) % 86400) * INTERVAL '1 second'
  END AS order_date,
  (ARRAY['pending','processing','shipped','delivered','delivered','delivered','delivered','cancelled','returned','processing'])[((n * 3) % 10) + 1] AS status,
  (ARRAY['credit_card','credit_card','credit_card','debit_card','debit_card','paypal','paypal','apple_pay','google_pay','cash','gift_card'])[((n * 11) % 11) + 1] AS payment_method,
  n::TEXT || ' Shipping Lane' AS shipping_address,
  (ARRAY['New York','Los Angeles','Chicago','Houston','Phoenix','London','Manchester','Toronto','Vancouver','Sydney','Melbourne','Brisbane'])[((n * 5) % 12) + 1] AS shipping_city,
  (ARRAY['US','US','US','US','US','US','US','US','US','US','GB','GB','CA','CA','AU','AU'])[((n * 7) % 16) + 1] AS shipping_country_id,
  -- subtotal: range $15 to $2500, realistic distribution
  ROUND((15 + (n * 173 % 2485))::NUMERIC, 2) AS subtotal,
  -- discount: 0 for most, some with promos
  CASE WHEN n % 5 = 0 THEN ROUND((5 + (n * 7 % 95))::NUMERIC, 2) ELSE 0.00 END AS discount_amount,
  -- shipping: free over $100, else $5-$15
  CASE WHEN (15 + (n * 173 % 2485)) >= 100 THEN 0.00 ELSE ROUND((4.99 + (n * 3 % 10))::NUMERIC, 2) END AS shipping_cost,
  -- tax: ~8.5% of subtotal
  ROUND(((15 + (n * 173 % 2485)) * 0.085)::NUMERIC, 2) AS tax_amount,
  -- total = subtotal - discount + shipping + tax
  -- DQ ISSUE 4: orders 4996-5000: total_amount < subtotal (bad data)
  CASE
    WHEN n >= 4996 THEN ROUND((15 + (n * 173 % 2485))::NUMERIC, 2) * 0.5  -- total < subtotal
    ELSE ROUND((
      (15 + (n * 173 % 2485))
      - CASE WHEN n % 5 = 0 THEN (5 + (n * 7 % 95)) ELSE 0 END
      + CASE WHEN (15 + (n * 173 % 2485)) >= 100 THEN 0.00 ELSE (4.99 + (n * 3 % 10)) END
      + (15 + (n * 173 % 2485)) * 0.085
    )::NUMERIC, 2)
  END AS total_amount,
  (ARRAY['USD','USD','USD','USD','USD','USD','USD','USD','USD','USD','GBP','GBP','CAD','CAD','AUD','AUD'])[((n * 7) % 16) + 1] AS currency_code,
  CASE WHEN n % 5 = 0 THEN
    (ARRAY['WELCOME10','FREESHIP','LOYALTY25','REFER20','SUMMER23','FALL23','TECH10','MOBILE10','BIRTHDAY20','EMPLOYEE15'])[((n * 3) % 10) + 1]
  ELSE NULL END AS promo_code,
  TIMESTAMP '2022-01-01' + ((n * 193) % 1095) * INTERVAL '1 day' AS created_at,
  TIMESTAMP '2022-01-01' + ((n * 193) % 1095) * INTERVAL '1 day' AS updated_at
FROM generate_series(1, 5000) AS n;

-- =============================================================================
-- SEED DATA: ORDER_ITEMS (15000 rows)
-- DQ ISSUE 3: 10 order_items with line_total = 0 (should be qty * unit_price)
-- =============================================================================
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct, line_total)
SELECT
  -- distribute 15000 items across 5000 orders (avg 3 items/order)
  ((n - 1) / 3) + 1 AS order_id,
  -- product_id 1-200 (we have ~117 products seeded above, cap at 117)
  ((n * 37) % 200) + 1 AS product_id,
  -- quantity 1-5
  ((n * 7) % 5) + 1 AS quantity,
  -- unit_price pulled from realistic range
  ROUND((9.99 + (n * 53 % 1790))::NUMERIC, 2) AS unit_price,
  -- discount_pct 0 for most
  CASE WHEN n % 8 = 0 THEN ROUND((5 + (n * 3 % 25))::NUMERIC, 2) ELSE 0.00 END AS discount_pct,
  -- DQ ISSUE 3: 10 items have line_total = 0
  CASE
    WHEN n IN (101, 202, 303, 404, 505, 606, 707, 808, 909, 1010) THEN 0.00
    ELSE ROUND((
      (((n * 7) % 5) + 1) *
      (9.99 + (n * 53 % 1790)) *
      (1 - CASE WHEN n % 8 = 0 THEN (5 + (n * 3 % 25))::NUMERIC / 100 ELSE 0 END)
    )::NUMERIC, 2)
  END AS line_total
FROM generate_series(1, 15000) AS n;

-- =============================================================================
-- SEED DATA: RETURNS (500 rows)
-- =============================================================================
INSERT INTO returns (order_id, order_item_id, return_date, reason, status, refund_amount, notes)
SELECT
  ((n * 11) % 5000) + 1 AS order_id,
  ((n * 13) % 15000) + 1 AS order_item_id,
  TIMESTAMP '2022-02-01' + ((n * 173) % 1050) * INTERVAL '1 day' AS return_date,
  (ARRAY['defective','wrong_item','not_as_described','changed_mind','damaged_shipping','other'])[((n * 7) % 6) + 1] AS reason,
  (ARRAY['requested','approved','received','refunded','refunded','refunded','rejected'])[((n * 3) % 7) + 1] AS status,
  ROUND((9.99 + (n * 43 % 490))::NUMERIC, 2) AS refund_amount,
  CASE
    WHEN n % 6 = 0 THEN 'Item arrived damaged, customer provided photos'
    WHEN n % 6 = 1 THEN 'Wrong size delivered, customer confirmed order details'
    WHEN n % 6 = 2 THEN 'Product does not match website description'
    WHEN n % 6 = 3 THEN 'Customer changed mind within return window'
    WHEN n % 6 = 4 THEN 'Packaging damaged in transit, product scratched'
    ELSE 'Other reason as provided by customer'
  END AS notes
FROM generate_series(1, 500) AS n;

-- =============================================================================
-- SEED DATA: EMPLOYEES (100 rows)
-- =============================================================================
INSERT INTO employees (employee_code, first_name, last_name, email, role, store_id, hire_date, salary, is_active)
SELECT
  'EMP-' || LPAD(n::TEXT, 5, '0') AS employee_code,
  (ARRAY['James','John','Robert','Michael','William','David','Joseph','Thomas','Charles','Christopher',
         'Emma','Olivia','Ava','Isabella','Sophia','Mia','Charlotte','Amelia','Harper','Evelyn',
         'Daniel','Matthew','Anthony','Mark','Donald','Anna','Maria','Lisa','Sarah','Jennifer',
         'Kevin','Brian','George','Edward','Ronald','Sandra','Betty','Dorothy','Carol','Ruth',
         'Larry','Paul','Andrew','Helen','Karen','Nancy','Margaret','Linda','Patricia','Barbara'])[((n-1) % 50) + 1] AS first_name,
  (ARRAY['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Martinez','Wilson',
         'Anderson','Taylor','Thomas','Hernandez','Moore','Martin','Jackson','Thompson','White','Lopez',
         'Lee','Gonzalez','Harris','Clark','Lewis','Robinson','Walker','Perez','Hall','Young',
         'Allen','Sanchez','Wright','King','Scott','Green','Baker','Adams','Nelson','Carter',
         'Mitchell','Roberts','Turner','Phillips','Campbell','Parker','Evans','Edwards','Collins','Stewart'])[((n-1) % 50) + 1] AS last_name,
  'emp' || n || '@retailhub.com' AS email,
  CASE
    WHEN n <= 30 THEN 'store_manager'
    WHEN n <= 60 THEN 'sales_associate'
    WHEN n <= 70 THEN 'warehouse'
    WHEN n <= 80 THEN 'analyst'
    WHEN n <= 92 THEN 'manager'
    ELSE 'director'
  END AS role,
  -- assign store_id 1-30 cycling, NULLs for directors/analysts
  CASE WHEN n <= 80 THEN ((n-1) % 30) + 1 ELSE NULL END AS store_id,
  (DATE '2015-01-01' + (n * 97 % 2920) * INTERVAL '1 day')::DATE AS hire_date,
  CASE
    WHEN n <= 30 THEN ROUND((55000 + (n * 1337 % 25000))::NUMERIC, 2)  -- managers
    WHEN n <= 60 THEN ROUND((28000 + (n * 997 % 15000))::NUMERIC, 2)   -- associates
    WHEN n <= 70 THEN ROUND((32000 + (n * 853 % 10000))::NUMERIC, 2)   -- warehouse
    WHEN n <= 80 THEN ROUND((65000 + (n * 1153 % 30000))::NUMERIC, 2)  -- analysts
    WHEN n <= 92 THEN ROUND((85000 + (n * 1327 % 40000))::NUMERIC, 2)  -- managers
    ELSE ROUND((120000 + (n * 1597 % 60000))::NUMERIC, 2)              -- directors
  END AS salary,
  CASE WHEN n % 10 = 0 THEN FALSE ELSE TRUE END AS is_active
FROM generate_series(1, 100) AS n;

-- =============================================================================
-- SEED DATA: INVENTORY_SNAPSHOTS (3000 rows)
-- Last 90 days, sampled across 200 products and 30 stores
-- =============================================================================
INSERT INTO inventory_snapshots (product_id, store_id, snapshot_date, quantity_on_hand, quantity_reserved, reorder_triggered)
SELECT
  ((n * 7) % 200) + 1 AS product_id,
  ((n * 11) % 30) + 1 AS store_id,
  (CURRENT_DATE - ((n * 3) % 90) * INTERVAL '1 day')::DATE AS snapshot_date,
  GREATEST(0, 50 - (n * 13 % 80)) AS quantity_on_hand,
  (n * 5 % 15) AS quantity_reserved,
  CASE WHEN GREATEST(0, 50 - (n * 13 % 80)) < 10 THEN TRUE ELSE FALSE END AS reorder_triggered
FROM generate_series(1, 3000) AS n;

-- =============================================================================
-- INDEXES
-- =============================================================================
CREATE INDEX idx_orders_customer_id       ON orders(customer_id);
CREATE INDEX idx_orders_order_date        ON orders(order_date);
CREATE INDEX idx_order_items_order_id     ON order_items(order_id);
CREATE INDEX idx_order_items_product_id   ON order_items(product_id);
CREATE INDEX idx_customers_email          ON customers(email) WHERE email IS NOT NULL;
CREATE INDEX idx_customers_country        ON customers(country_id);
CREATE INDEX idx_inventory_snapshots_date ON inventory_snapshots(snapshot_date);
CREATE INDEX idx_products_category        ON products(category_id);
CREATE INDEX idx_products_supplier        ON products(supplier_id);
CREATE INDEX idx_orders_store_id          ON orders(store_id);
CREATE INDEX idx_returns_order_id         ON returns(order_id);
CREATE INDEX idx_employees_store_id       ON employees(store_id);

-- =============================================================================
-- VERIFICATION COUNTS (informational)
-- =============================================================================
-- SELECT 'countries'           AS tbl, COUNT(*) FROM countries
-- UNION ALL SELECT 'stores',              COUNT(*) FROM stores
-- UNION ALL SELECT 'product_categories',  COUNT(*) FROM product_categories
-- UNION ALL SELECT 'suppliers',           COUNT(*) FROM suppliers
-- UNION ALL SELECT 'products',            COUNT(*) FROM products
-- UNION ALL SELECT 'customers',           COUNT(*) FROM customers
-- UNION ALL SELECT 'promotions',          COUNT(*) FROM promotions
-- UNION ALL SELECT 'orders',              COUNT(*) FROM orders
-- UNION ALL SELECT 'order_items',         COUNT(*) FROM order_items
-- UNION ALL SELECT 'returns',             COUNT(*) FROM returns
-- UNION ALL SELECT 'employees',           COUNT(*) FROM employees
-- UNION ALL SELECT 'inventory_snapshots', COUNT(*) FROM inventory_snapshots;
