"""실습 3 : 데드락 재현과 해결

두 트랜잭션이 서로 반대 순서로 행을 잠그면 영원히 기다리게 된다 (데드락).
InnoDB 는 이를 감지해서 한쪽을 강제로 롤백한다 (에러 1213).

  T1 : 계좌 1 잠금 → 계좌 2 잠금 시도
  T2 : 계좌 2 잠금 → 계좌 1 잠금 시도     ← 서로 상대가 쥔 행을 기다림

해결 : 항상 같은 순서(예: id 오름차순)로 잠근다.

실행: python 03_deadlock.py        (먼저 python 00_seed.py)
"""
import threading
import time

import pymysql

from common import connect, query


def transfer(name, first, second, barrier, results):
    # barrier : 서로 반대 순서로 잠그는 경우에만 쓴다 (둘 다 첫 행을 쥔 다음에 두 번째 행으로 넘어가게 맞춤)
    conn = connect(autocommit=False)
    try:
        query(conn, "START TRANSACTION")
        query(conn, "SELECT * FROM account WHERE id = %s FOR UPDATE", (first,))     # 첫 번째 행을 잠금
        if barrier is not None:
            barrier.wait()                                                          # 둘 다 첫 행을 잡을 때까지 기다림
        time.sleep(0.2)
        query(conn, "SELECT * FROM account WHERE id = %s FOR UPDATE", (second,))    # 두 번째 행: 상대가 쥐고 있음
        conn.commit()
        results[name] = "성공(커밋)"
    except pymysql.err.OperationalError as e:
        code = e.args[0]
        results[name] = f"실패 에러 {code} : {e.args[1]}" + ("   ← 데드락 희생자로 선택되어 롤백됨" if code == 1213 else "")
        conn.rollback()
    finally:
        conn.close()


def run(title, order_t1, order_t2, use_barrier):
    print(f"\n{title}")
    barrier, results = (threading.Barrier(2) if use_barrier else None), {}
    started = time.perf_counter()
    t1 = threading.Thread(target=transfer, args=("T1", *order_t1, barrier, results))
    t2 = threading.Thread(target=transfer, args=("T2", *order_t2, barrier, results))
    t1.start(); t2.start(); t1.join(); t2.join()
    for name in ("T1", "T2"):
        print(f"  {name} ({'→'.join(map(str, order_t1 if name == 'T1' else order_t2))} 순서로 잠금): {results[name]}")
    print(f"  걸린 시간 {time.perf_counter() - started:.1f}초")


run("[1] 반대 순서로 잠그면", (1, 2), (2, 1), use_barrier=True)
run("[2] 둘 다 같은 순서(1 → 2)로 잠그면", (1, 2), (1, 2), use_barrier=False)   # 먼저 잡은 쪽이 끝나면 나머지가 이어서 진행
