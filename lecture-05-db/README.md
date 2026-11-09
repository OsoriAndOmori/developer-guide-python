# 5강. DB 실습 : 인덱스, 격리와 락, 데드락, 커넥션 풀, 트랜잭션

블로그 [내 맘대로 팀 입사 교육과정](https://osoriandomori.github.io/posts/%EB%82%B4-%EB%A7%98%EB%8C%80%EB%A1%9C-%ED%8C%80-%EC%9E%85%EC%82%AC-%EA%B5%90%EC%9C%A1%EA%B3%BC%EC%A0%95/) 5장(DB)의 공통 개념을
MySQL 8 (InnoDB)에서 직접 확인하고, 파이썬(SQLAlchemy, PyMySQL, FastAPI)에서 어떻게 다루는지 본다.

## 준비

```bash
cd lecture-05-db
docker compose up -d                       # MySQL 8.4 + DB 웹 화면(Adminer)
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
python 00_seed.py                          # orders 30만 건, account 2건 생성 (다시 실행하면 새로 만듦)
# DB 웹 화면 : http://localhost:8082  (서버 mysql / 사용자 root / 비밀번호 root / DB lecture05)
# 끝나면: docker compose down
```

- MySQL 은 내 컴퓨터의 3306 과 겹치지 않게 **3307** 로 연다. 슬로우 쿼리 로그(0.2초 이상)도 켜 두었다.
- 실습마다 스크립트 맨 위 설명에 무엇을 보려는지 적어 두었다.

## 공통 개념 → 실습 대응

| 실습 | 공통편 5장의 개념 | 실행 |
|---|---|---|
| `01_explain_index.py` | 인덱스, 실행계획(EXPLAIN), cardinality, 복합 인덱스 순서, 커버링 인덱스 | `python 01_explain_index.py` |
| `02_isolation_lock.py` | 격리 수준, MVCC, 갱신 손실, `SELECT ... FOR UPDATE`, 낙관/비관 락 | `python 02_isolation_lock.py` |
| `03_deadlock.py` | 락, 데드락과 해결(잠금 순서 통일) | `python 03_deadlock.py` |
| `04_pool.py` | 커넥션 풀 크기, 풀 고갈, 트랜잭션 안에서 외부 호출 금지 | `python 04_pool.py` |
| `05_transactional.py` | 트랜잭션 경계, 전파(참여), SAVEPOINT | `python 05_transactional.py` |
| `06_fastapi_session.py` | 요청 단위 트랜잭션(세션) | `python 06_fastapi_session.py` |
| `07_bulk_stream.py` | 대량 insert, 큰 결과 읽기(OLAP 쪽 습관) | `python 07_bulk_stream.py` |

## 결과 (이 컴퓨터, MySQL 8.4 / Docker)

**01. 인덱스와 실행계획** (쿼리 20번 반복)

| 상황 | EXPLAIN | 시간 |
|---|---|---|
| `user_id` 인덱스 없음 | `type=ALL`, 훑는 행 약 29.8만 | 0.372초 |
| `user_id` 인덱스 있음 | `type=ref`, 훑는 행 25 | **0.007초** (약 50배) |
| 값이 3종류뿐인 `status` 에 인덱스 | 14.9만 행을 훑음 | 0.159초 (큰 도움 안 됨) |
| `(status, user_id)` 인덱스로 `user_id` 만 조회 | **인덱스 못 씀**(`type=ALL`) | - |
| `(user_id, status)` 인덱스로 `user_id` 만 조회 | 인덱스 사용 | - |
| 필요한 컬럼이 전부 인덱스 안 | `Extra: Using index` (커버링) | - |

**02. 격리와 락**
- `READ COMMITTED` 에서는 같은 트랜잭션 안에서 읽은 값이 1000 → 900 으로 **바뀐다**. `REPEATABLE READ`(MySQL 기본)에서는 1000 그대로(스냅샷).
- 락 없이 둘이 +100 하면 기대 1200 인데 **1100** (갱신 손실). `SELECT ... FOR UPDATE` 는 B 가 1.0초 기다린 뒤 A 의 결과를 보고 **1200**. `UPDATE ... SET balance = balance + 100` 한 줄이면 락을 직접 다루지 않고도 1200.

**03. 데드락**
- 반대 순서(1→2, 2→1)로 잠그면 InnoDB 가 한쪽을 골라 **에러 1213** 으로 롤백. 같은 순서로 잠그면 모두 성공.

**04. 풀과 외부 호출**
- 풀 2개에 연결을 2초씩 쥐는 요청 5개 → 2개만 처리, 나머지 3개는 **풀 타임아웃**(`QueuePool limit of size 2 overflow 0 reached`).
- 외부 호출(1초)을 트랜잭션 **안**에서 하면: 서로 다른 행이면 풀이 병목이라 **3.1초**, 같은 행이면 행 락 때문에 **6.1초**. **밖**에서 하면 둘 다 **1.0초**.

**05. 트랜잭션 묶기**
- `with Session.begin()` : 성공하면 커밋, 예외면 롤백.
- `@transactional` 데코레이터(`contextvars` 로 현재 세션 전달): 안쪽 호출이 바깥 트랜잭션에 **참여**하면 입금 실패 시 출금도 롤백 `[1000, 1000]`. 각자 트랜잭션이면 출금만 커밋되어 돈이 사라짐 `[700, 1000]`.
- `begin_nested()`(SAVEPOINT): 안쪽만 롤백되고 바깥은 커밋.

**07. 대량 insert와 큰 결과**
- 3,000건 insert: 한 건씩 커밋 **2.1초** vs `executemany` + 한 번 커밋 **0.02초**.
- 30만 행 읽기: `fetchall` 은 최대 메모리 **약 107MB**, 서버 사이드 커서(`SSCursor`)는 **약 0.3MB**.

## 이 실습에서 파이썬 특화로 볼 것

- 동기 드라이버(`PyMySQL`)는 `async def` 안에서 부르면 이벤트루프를 막는다. FastAPI 에서는 `def` 엔드포인트(스레드풀)로 쓰거나 비동기 드라이버(`aiomysql`, `asyncmy`)를 써야 한다.
- **세션은 스레드 안전하지 않다.** 전역 하나를 공유하지 말고 요청마다 하나씩 만든다(06번의 `Depends`).
- 현재 세션을 함수 인자로 넘기지 않으려면 `contextvars` 를 쓴다(05번의 `@transactional`).
- `SQLAlchemy` 의 풀 설정(`pool_size`, `max_overflow`, `pool_timeout`)은 워커 수와 함께 계산한다: **워커 수 × (pool_size + max_overflow) ≤ DB max_connections**.

## 운영 감각 (슬로우 쿼리 로그)

```bash
docker exec lecture05-mysql sh -c 'tail -n 20 /var/lib/mysql/*-slow.log'
```
- 0.2초 이상 걸린 쿼리가 `Query_time`, `Rows_examined` 와 함께 남는다. 풀 스캔이 `Rows_examined` 가 큰 것으로 바로 보인다.
