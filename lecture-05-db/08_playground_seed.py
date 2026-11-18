"""DataGrip 등으로 바로 조회해 볼 놀이터 데이터를 만든다. (실습 01~07 이 쓰는 orders/account 는 건드리지 않는다)

  users      : 사용자 1만 명
  products   : 상품 200개 (카테고리 8종)
  sales      : 판매 내역 50만 건, 월별 RANGE 파티션 (2026-01 ~ 2026-12)
  sales_flat : sales 와 같은 데이터, 파티션 없음  -> 같은 쿼리로 EXPLAIN 비교용

접속: localhost:3307 / root / root / DB lecture05
쿼리 모음: playground.sql

실행: python 08_playground_seed.py
"""
import random

from common import connect, timed

SALES = 500_000
CATEGORIES = ["food", "book", "toy", "fashion", "beauty", "sports", "home", "digital"]
CITIES = ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Ulsan", "Jeju"]
STATUSES = ["PAID"] * 8 + ["SHIPPED"] * 6 + ["CANCELED"]

random.seed(11)
conn = connect()
with conn.cursor() as cur:
    for t in ("sales", "sales_flat", "users", "products"):
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    cur.execute("""CREATE TABLE users (
        id INT PRIMARY KEY, name VARCHAR(30) NOT NULL, city VARCHAR(10) NOT NULL,
        joined_at DATE NOT NULL, KEY idx_city (city))""")
    cur.execute("""CREATE TABLE products (
        id INT PRIMARY KEY, name VARCHAR(30) NOT NULL, category VARCHAR(10) NOT NULL,
        price INT NOT NULL)""")
    cols = """id BIGINT NOT NULL AUTO_INCREMENT, user_id INT NOT NULL, product_id INT NOT NULL,
        qty INT NOT NULL, amount INT NOT NULL, status VARCHAR(10) NOT NULL, created_at DATETIME NOT NULL"""
    parts = ",\n".join(
        f"PARTITION p{m:02d} VALUES LESS THAN (TO_DAYS('2026-{m + 1:02d}-01'))" for m in range(1, 12)
    ) + ",\nPARTITION p12 VALUES LESS THAN (TO_DAYS('2027-01-01'))"
    # 파티션 키(created_at)는 PK 에 포함돼야 한다
    cur.execute(f"""CREATE TABLE sales ({cols},
        PRIMARY KEY (id, created_at), KEY idx_user (user_id), KEY idx_product (product_id))
        PARTITION BY RANGE (TO_DAYS(created_at)) ({parts})""")
    cur.execute(f"""CREATE TABLE sales_flat ({cols},
        PRIMARY KEY (id, created_at), KEY idx_user (user_id), KEY idx_product (product_id))""")

users = [(i, f"user{i:05d}", random.choice(CITIES),
          f"2025-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}") for i in range(1, 10_001)]
products = [(i, f"{CATEGORIES[i % 8]}-item-{i:03d}", CATEGORIES[i % 8],
             random.randint(5, 300) * 100) for i in range(1, 201)]
price = {p[0]: p[3] for p in products}

sales = []
for i in range(1, SALES + 1):
    pid = random.randint(1, 200)
    qty = random.randint(1, 5)
    m = random.choices(range(1, 13), weights=[5, 5, 6, 6, 7, 8, 8, 9, 9, 10, 12, 15])[0]
    sales.append((i, random.randint(1, 10_000), pid, qty, price[pid] * qty, random.choice(STATUSES),
                  f"2026-{m:02d}-{random.randint(1, 28):02d} {random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00"))

with timed("insert"):
    conn.autocommit(False)
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO users VALUES (%s,%s,%s,%s)", users)
        cur.executemany("INSERT INTO products VALUES (%s,%s,%s,%s)", products)
        for t in ("sales", "sales_flat"):
            for i in range(0, SALES, 10_000):
                cur.executemany(f"INSERT INTO {t} VALUES (%s,%s,%s,%s,%s,%s,%s)", sales[i:i + 10_000])
    conn.commit()
with conn.cursor() as cur:
    for t in ("users", "products", "sales", "sales_flat"):
        cur.execute(f"ANALYZE TABLE {t}")
        cur.fetchall()
print("완료: users 10,000 / products 200 / sales 500,000 / sales_flat 500,000")
