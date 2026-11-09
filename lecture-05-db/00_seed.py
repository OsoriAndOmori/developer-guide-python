"""실습용 테이블과 데이터를 만든다. (처음 한 번만, 다시 실행하면 새로 만든다)

  orders  : 주문 30만 건 (user_id 는 1~10,000 사이, status 는 3종류) - 인덱스/실행계획 실습
  account : 계좌 2개                                               - 트랜잭션/락/격리 실습

실행: python 00_seed.py
"""
import random

from common import connect, timed

ORDERS = 300_000

conn = connect()
with conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS orders")
    cur.execute("DROP TABLE IF EXISTS account")
    cur.execute("""
        CREATE TABLE orders (
            id         BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id    INT NOT NULL,
            status     VARCHAR(10) NOT NULL,
            amount     INT NOT NULL,
            created_at DATETIME NOT NULL,
            memo       VARCHAR(100) NOT NULL
        ) ENGINE=InnoDB
    """)
    cur.execute("CREATE TABLE account (id INT PRIMARY KEY, balance INT NOT NULL) ENGINE=InnoDB")
    cur.execute("INSERT INTO account VALUES (1, 1000), (2, 1000)")

random.seed(7)
statuses = ["PAID", "SHIPPED", "CANCELED"]
rows = [
    (random.randint(1, 10_000), random.choice(statuses), random.randint(1, 100) * 100,
     f"2026-{random.randint(1, 10):02d}-{random.randint(1, 28):02d} 12:00:00", "x" * 50)
    for _ in range(ORDERS)
]
with timed(f"orders {ORDERS:,}건 insert (executemany, 한 트랜잭션)"):
    conn.autocommit(False)
    with conn.cursor() as cur:
        for i in range(0, ORDERS, 10_000):
            cur.executemany(
                "INSERT INTO orders (user_id, status, amount, created_at, memo) VALUES (%s,%s,%s,%s,%s)",
                rows[i:i + 10_000],
            )
    conn.commit()
with conn.cursor() as cur:
    cur.execute("ANALYZE TABLE orders")
    cur.fetchall()
print("완료: orders", ORDERS, "건, account 2건")
