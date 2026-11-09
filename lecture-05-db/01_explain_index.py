"""실습 1 : 인덱스와 실행계획 (EXPLAIN)

같은 쿼리가 인덱스가 있을 때와 없을 때 어떻게 다른지, EXPLAIN 으로 DB 가 어떻게 찾는지 본다.
  type=ALL   : 테이블 전체를 훑음 (풀스캔)
  type=ref   : 인덱스로 해당 값만 찾음
  Extra=Using index : 테이블을 안 읽고 인덱스만으로 답함 (커버링 인덱스)

실행: python 01_explain_index.py        (먼저 python 00_seed.py)
"""
from common import connect, query, timed

conn = connect()
REPEAT = 20


def drop_indexes():
    for name in ("idx_user", "idx_status", "idx_user_status", "idx_status_user"):
        try:
            query(conn, f"DROP INDEX {name} ON orders")
        except Exception:
            pass


def explain(sql):
    row = query(conn, "EXPLAIN " + sql)[0]
    print(f"    EXPLAIN → type={row['type']}, key={row['key']}, 훑는 행 수(추정)={row['rows']:,}, Extra={row['Extra']}")


def run(label, sql, args=()):
    explain(sql % args if args else sql)
    with timed(f"{label} (x{REPEAT})"):
        for _ in range(REPEAT):
            query(conn, sql, args or None)


Q_USER = "SELECT COUNT(*) AS c, SUM(amount) AS s FROM orders WHERE user_id = 4242"
Q_STATUS = "SELECT COUNT(*) AS c FROM orders WHERE status = 'CANCELED'"
Q_BOTH = "SELECT COUNT(*) AS c FROM orders WHERE user_id = 4242 AND status = 'PAID'"
Q_COVER = "SELECT user_id, status FROM orders WHERE user_id = 4242"

drop_indexes()
print("\n[1] 인덱스가 없을 때 : user_id 로 찾기")
run("user_id = 4242, 인덱스 없음", Q_USER)

print("\n[2] user_id 에 인덱스를 만들면")
query(conn, "CREATE INDEX idx_user ON orders (user_id)")
run("user_id = 4242, 인덱스 있음", Q_USER)

print("\n[3] 값의 종류가 적은 컬럼(status, 3종류)에 인덱스를 만들면?  (cardinality 가 낮다)")
query(conn, "CREATE INDEX idx_status ON orders (status)")
run("status = 'CANCELED', 인덱스 있음", Q_STATUS)
print("    → 전체의 1/3 을 읽어야 해서 인덱스가 큰 도움이 안 된다 (값을 골고루 가진 컬럼이 좋다)")

print("\n[4] 복합 인덱스는 컬럼 순서가 중요하다 (왼쪽부터 쓰인다)")
drop_indexes()
query(conn, "CREATE INDEX idx_status_user ON orders (status, user_id)")
print("  (status, user_id) 인덱스로 user_id 만 조건에 쓰면:")
explain(Q_USER)
drop_indexes()
query(conn, "CREATE INDEX idx_user_status ON orders (user_id, status)")
print("  (user_id, status) 인덱스로 user_id 만 조건에 쓰면:")
explain(Q_USER)
print("  (user_id, status) 인덱스로 두 컬럼 모두 조건에 쓰면:")
run("user_id AND status", Q_BOTH)

print("\n[5] 커버링 인덱스 : 필요한 컬럼이 전부 인덱스 안에 있으면 테이블을 읽지 않는다")
run("SELECT user_id, status (user_id, status 인덱스)", Q_COVER)
print("    → Extra 에 'Using index' 가 보이면 커버링 인덱스")

drop_indexes()
