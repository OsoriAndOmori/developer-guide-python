"""실습 4 : 커넥션 풀 고갈과 "트랜잭션 안에서 외부 호출" 함정

SQLAlchemy 의 연결 풀(QueuePool)을 아주 작게(2개) 만들어서 풀이 부족하면 무슨 일이 생기는지 본다.

A) 풀이 2개인데 연결을 오래 쥐는 요청이 5개 몰리면 → 나머지는 기다리다가 타임아웃
B) 같은 일을 "외부 호출을 트랜잭션 안에서 한 경우" vs "트랜잭션 밖에서 한 경우"로 비교
   (외부 호출 = S3, 다른 서비스 API 같은 느린 일을 sleep 으로 흉내)

실행: python 04_pool.py        (먼저 python 00_seed.py)
"""
import threading
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import TimeoutError as PoolTimeout

from common import URL

EXTERNAL = 1.0   # 외부 호출이 걸리는 시간(초)


def make_engine(pool_timeout):
    # pool_size=2 : 연결 2개만 만들어 두고 재사용, max_overflow=0 : 그 이상은 만들지 않음
    return create_engine(URL, pool_size=2, max_overflow=0, pool_timeout=pool_timeout)


def run_threads(n, target):
    results, started = {}, time.perf_counter()
    threads = [threading.Thread(target=target, args=(i, results, started)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, time.perf_counter() - started


# ── A) 풀 고갈 ─────────────────────────────────────────────
print("\n[A] 풀 크기 2, 연결을 2초씩 쥐는 요청 5개, 풀에서 연결을 기다리는 한도(pool_timeout) 1초")
engine = make_engine(pool_timeout=1)


def hold_connection(i, results, started):
    try:
        with engine.connect() as conn:                          # 풀에서 연결을 빌린다 (없으면 기다림)
            got = time.perf_counter() - started
            conn.execute(text("SELECT SLEEP(2)"))               # 느린 쿼리를 흉내
            results[i] = f"연결을 {got:.1f}초에 얻어서 처리 완료"
    except PoolTimeout as e:
        results[i] = f"풀 타임아웃 : {str(e).split(' (')[0]}"


results, total = run_threads(5, hold_connection)
for i in sorted(results):
    print(f"  요청 {i}: {results[i]}")
engine.dispose()

# ── B) 외부 호출 위치 ───────────────────────────────────────
print(f"\n[B] 풀 크기 2, 요청 6개, 각 요청은 '외부 호출 {EXTERNAL:.0f}초 + DB 업데이트' 를 한다")
engine = make_engine(pool_timeout=30)


def update_sql(i, same_row):
    # same_row=True : 모두 같은 행(account 1)을 수정 → 행 락 때문에 서로 기다림
    # same_row=False: 요청마다 다른 행을 수정 → 락은 겹치지 않고 풀 크기만 영향을 줌
    if same_row:
        return text("UPDATE account SET balance = balance + 1 WHERE id = 1")
    return text(f"UPDATE orders SET amount = amount + 1 WHERE id = {i + 1}")


def make_inside(same_row):
    def external_inside(i, results, started):                   # 나쁜 예 : 연결(트랜잭션)을 쥔 채로 외부 호출
        with engine.begin() as conn:
            conn.execute(update_sql(i, same_row))
            time.sleep(EXTERNAL)                                # 이 동안 연결과 (수정한 행의) 락을 계속 쥐고 있다
        results[i] = time.perf_counter() - started
    return external_inside


def make_outside(same_row):
    def external_outside(i, results, started):                  # 좋은 예 : 외부 호출을 먼저 끝내고 짧게 트랜잭션
        time.sleep(EXTERNAL)
        with engine.begin() as conn:
            conn.execute(update_sql(i, same_row))
        results[i] = time.perf_counter() - started
    return external_outside


rows = [
    ("서로 다른 행을 수정 (락 충돌 없음)", False, "연결 2개를 3번 돌려쓰느라 줄을 섬 (풀이 병목)"),
    ("모두 같은 행을 수정", True, "행 락 때문에 6개가 한 줄로 섬 (락이 병목, 풀 크기와 무관)"),
]
for title, same_row, why in rows:
    _, t_in = run_threads(6, make_inside(same_row))
    _, t_out = run_threads(6, make_outside(same_row))
    print(f"  [{title}]")
    print(f"    트랜잭션 '안'에서 외부 호출 : 전체 {t_in:.1f}초   ← {why}")
    print(f"    트랜잭션 '밖'에서 외부 호출 : 전체 {t_out:.1f}초   ← 연결과 락을 잠깐만 쥐어서 6개가 동시에 진행")
engine.dispose()
