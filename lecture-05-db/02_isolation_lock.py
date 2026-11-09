"""실습 2 : 격리 수준과 락 (연결 두 개로 두 사용자를 흉내 냄)

A) 같은 트랜잭션 안에서 같은 행을 두 번 읽으면? (READ COMMITTED vs REPEATABLE READ)
B) 둘이 동시에 잔액을 읽고 +100 씩 하면? (갱신 손실) → SELECT ... FOR UPDATE 로 막기, 한 줄 UPDATE 로 풀기

실행: python 02_isolation_lock.py        (먼저 python 00_seed.py)
"""
import threading
import time

from common import connect, query


def balance(conn):
    return query(conn, "SELECT balance FROM account WHERE id = 1")[0]["balance"]


def reset():
    c = connect()
    query(c, "UPDATE account SET balance = 1000 WHERE id = 1")
    c.close()


def part_a(level):
    reset()
    a, b = connect(autocommit=False), connect(autocommit=True)
    query(a, f"SET SESSION TRANSACTION ISOLATION LEVEL {level}")
    query(a, "START TRANSACTION")
    first = balance(a)
    query(b, "UPDATE account SET balance = 900 WHERE id = 1")   # 다른 사용자가 수정하고 커밋
    second = balance(a)
    print(f"  {level:<16} A 가 읽은 값: 처음 {first} → (B 가 900 으로 커밋) → 다시 {second}"
          + ("   ← 같은 트랜잭션인데 값이 바뀜(non-repeatable read)" if first != second else "   ← 트랜잭션 시작 시점 그대로(스냅샷)"))
    a.rollback(); a.close(); b.close()


print("\n[A] 같은 트랜잭션 안에서 두 번 읽기 (MySQL 기본은 REPEATABLE READ)")
part_a("READ COMMITTED")
part_a("REPEATABLE READ")

print("\n[B-1] 락 없이 '읽고 → 계산하고 → 쓰기' 를 둘이 동시에 하면 (갱신 손실, lost update)")
reset()
a, b = connect(autocommit=False), connect(autocommit=False)
query(a, "START TRANSACTION"); query(b, "START TRANSACTION")
ra, rb = balance(a), balance(b)                                   # 둘 다 1000 을 읽음
query(a, "UPDATE account SET balance = %s WHERE id = 1", (ra + 100,)); a.commit()
query(b, "UPDATE account SET balance = %s WHERE id = 1", (rb + 100,)); b.commit()
c = connect()
print(f"  A, B 가 각각 +100 → 기대 1200, 실제 {balance(c)}   ← 한 번의 +100 이 사라짐")
a.close(); b.close(); c.close()

print("\n[B-2] SELECT ... FOR UPDATE 로 행을 잠그면 (비관적 락)")
reset()
a, b = connect(autocommit=False), connect(autocommit=False)
log = []

def worker_b():
    query(b, "START TRANSACTION")
    t = time.perf_counter()
    rb = query(b, "SELECT balance FROM account WHERE id = 1 FOR UPDATE")[0]["balance"]   # A 가 잡고 있으면 여기서 기다린다
    log.append(f"B 는 {time.perf_counter() - t:.1f}초 기다렸다가 {rb} 를 읽음 (A 의 결과를 본 값)")
    query(b, "UPDATE account SET balance = %s WHERE id = 1", (rb + 100,)); b.commit()

query(a, "START TRANSACTION")
ra = query(a, "SELECT balance FROM account WHERE id = 1 FOR UPDATE")[0]["balance"]   # A 가 행을 잠금
th = threading.Thread(target=worker_b); th.start()
time.sleep(1.0)                                                                       # B 가 막혀서 기다리는 중
query(a, "UPDATE account SET balance = %s WHERE id = 1", (ra + 100,)); a.commit()    # A 커밋 → 락 해제
th.join()
c = connect()
print("  " + log[0])
print(f"  최종 잔액 {balance(c)}   ← 둘 다 반영됨")
a.close(); b.close(); c.close()

print("\n[B-3] 가장 단순한 해법 : 읽지 말고 DB 에서 한 줄로 계산 (UPDATE ... SET balance = balance + 100)")
reset()
a, b = connect(), connect()
query(a, "UPDATE account SET balance = balance + 100 WHERE id = 1")
query(b, "UPDATE account SET balance = balance + 100 WHERE id = 1")
print(f"  최종 잔액 {balance(a)}   ← 락을 직접 다루지 않아도 정확")
a.close(); b.close()
reset()
