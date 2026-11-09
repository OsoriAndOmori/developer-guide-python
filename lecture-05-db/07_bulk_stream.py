"""실습 7 : 데이터팀 실습 - 대량 insert 와 큰 결과 읽기

A) 대량 insert : 한 건씩 커밋 vs 모아서(executemany) 한 트랜잭션
B) 큰 결과 읽기 : 기본 커서(결과 전부를 메모리에 올림) vs 서버 사이드 커서 SSCursor (한 줄씩 흘려 받음)

실행: python 07_bulk_stream.py        (먼저 python 00_seed.py)
"""
import time
import tracemalloc

import pymysql

from common import connect, query, timed

N = 3_000
conn = connect()
query(conn, "DROP TABLE IF EXISTS bulk_test")
query(conn, "CREATE TABLE bulk_test (id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, amount INT NOT NULL) ENGINE=InnoDB")
rows = [(i % 1000, i) for i in range(N)]

print(f"\n[A] {N:,}건 insert")
conn.autocommit(True)
with timed("한 건씩 insert + 매번 커밋(autocommit)"):
    with conn.cursor() as cur:
        for r in rows:
            cur.execute("INSERT INTO bulk_test (user_id, amount) VALUES (%s, %s)", r)   # 건마다 디스크 flush(redo 로그)
query(conn, "TRUNCATE TABLE bulk_test")
conn.autocommit(False)
with timed("한 트랜잭션 + executemany (한 번에 커밋)"):
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO bulk_test (user_id, amount) VALUES (%s, %s)", rows)  # 여러 행을 묶어서 보냄
    conn.commit()
conn.autocommit(True)
query(conn, "DROP TABLE bulk_test")
print("    → 왕복(RTT)과 건마다의 커밋(로그 flush) 비용이 건수만큼 곱해지는 것이 차이의 원인")

print("\n[B] orders 30만 건 읽기 : 메모리를 얼마나 쓰나 (Python 이 할당한 최대 메모리)")


def read_all():
    c = connect(cursorclass=pymysql.cursors.Cursor)   # 기본 커서(Cursor): 쿼리 결과 전부를 클라이언트 메모리에 올린다 (행은 튜플)
    with c.cursor() as cur:
        cur.execute("SELECT id, user_id, status, amount, created_at, memo FROM orders")
        total = len(cur.fetchall())
    c.close()
    return total


def read_stream():
    c = connect(cursorclass=pymysql.cursors.SSCursor)  # 서버 사이드 커서: 서버가 결과를 흘려 주고 한 줄씩 받음 (행은 튜플)
    total = 0
    with c.cursor() as cur:
        cur.execute("SELECT id, user_id, status, amount, created_at, memo FROM orders")
        for _ in cur:
            total += 1
    c.close()
    return total


for label, fn in (("기본 커서 (fetchall)", read_all), ("SSCursor (한 줄씩)", read_stream)):
    tracemalloc.start()
    started = time.perf_counter()
    total = fn()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  {label:<22} {total:,}행, {elapsed:5.2f}초, 최대 메모리 {peak / 1024 / 1024:7.1f}MB")
print("    → 큰 결과를 한꺼번에 올리면 메모리가 결과 크기만큼 필요. 스트리밍은 일정하게 유지(대신 연결을 오래 쥠)")
