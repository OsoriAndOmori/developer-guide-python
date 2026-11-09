"""실습 5 : 파이썬에서 트랜잭션 묶기 (스프링 @Transactional 과 비교)

A) 컨텍스트 매니저 (with) : 가장 파이썬스러운 명시적 방식
B) 데코레이터 @transactional : 함수 전체를 트랜잭션으로 (스프링 @Transactional 과 같은 역할)
   - 이미 트랜잭션 안이면 그 트랜잭션에 "참여" (REQUIRED). 현재 세션은 contextvars 로 전달한다
   - 참여하지 않고 각자 트랜잭션을 가지면 어떤 일이 생기는지도 비교한다
C) 중첩 트랜잭션 : SAVEPOINT (begin_nested) 로 일부만 롤백

실행: python 05_transactional.py        (먼저 python 00_seed.py)
"""
import contextvars
import functools

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from common import URL

engine = create_engine(URL)


def balances():
    with engine.connect() as c:
        return [r[0] for r in c.execute(text("SELECT balance FROM account ORDER BY id"))]


def reset():
    with engine.begin() as c:
        c.execute(text("UPDATE account SET balance = 1000"))


# ── A) 컨텍스트 매니저 ──────────────────────────────────────
def transfer_with(src, dst, amount, fail=False):
    with Session(engine) as session, session.begin():           # 블록이 끝나면 커밋, 예외가 나면 롤백
        session.execute(text("UPDATE account SET balance = balance - :a WHERE id = :i"), {"a": amount, "i": src})
        if fail:
            raise RuntimeError("출금 후 입금 전에 실패!")
        session.execute(text("UPDATE account SET balance = balance + :a WHERE id = :i"), {"a": amount, "i": dst})


print("\n[A] with Session.begin() : 성공하면 커밋, 예외가 나면 롤백")
reset()
transfer_with(1, 2, 300)
print("  성공 이체 후 :", balances())
try:
    transfer_with(1, 2, 300, fail=True)
except RuntimeError as e:
    print(f"  실패 이체 후 : {balances()}   ← 예외({e})로 롤백, 출금만 되고 끝나는 일이 없음")

# ── B) 데코레이터 + 현재 세션 전달 ──────────────────────────
_current = contextvars.ContextVar("current_session", default=None)


def transactional(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if _current.get() is not None:                          # 이미 트랜잭션 안 → 참여 (REQUIRED)
            return func(*args, **kwargs)
        with Session(engine) as session, session.begin():       # 없으면 새로 시작
            token = _current.set(session)
            try:
                return func(*args, **kwargs)
            finally:
                _current.reset(token)
    return wrapper


def _exec(sql, **params):
    return _current.get().execute(text(sql), params)


@transactional
def withdraw(i, amount):
    _exec("UPDATE account SET balance = balance - :a WHERE id = :i", a=amount, i=i)


@transactional
def deposit(i, amount, fail=False):
    if fail:
        raise RuntimeError("입금 단계 실패!")
    _exec("UPDATE account SET balance = balance + :a WHERE id = :i", a=amount, i=i)


@transactional                                                   # 바깥 함수가 트랜잭션을 열고, 안쪽 withdraw/deposit 은 참여
def transfer_joined(src, dst, amount, fail=False):
    withdraw(src, amount)
    deposit(dst, amount, fail=fail)


def transfer_separate(src, dst, amount, fail=False):             # 바깥에 @transactional 이 없음 → 각 호출이 자기 트랜잭션을 가짐
    withdraw(src, amount)
    deposit(dst, amount, fail=fail)


print("\n[B] @transactional : 안쪽 호출이 바깥 트랜잭션에 참여하느냐에 따라 결과가 갈린다")
reset()
try:
    transfer_joined(1, 2, 300, fail=True)
except RuntimeError:
    pass
print(f"  바깥에 @transactional (참여)   : {balances()}   ← 입금 실패로 출금도 같이 롤백")
reset()
try:
    transfer_separate(1, 2, 300, fail=True)
except RuntimeError:
    pass
print(f"  바깥에 없음 (각자 트랜잭션)    : {balances()}   ← 출금은 이미 커밋되어 돈이 사라짐 (합계 {sum(balances())})")

# ── C) 중첩 트랜잭션 (SAVEPOINT) ────────────────────────────
print("\n[C] 중첩 트랜잭션 : 일부만 롤백하고 바깥은 계속")
reset()
with Session(engine) as session, session.begin():
    session.execute(text("UPDATE account SET balance = balance - 100 WHERE id = 1"))
    try:
        with session.begin_nested():                             # SAVEPOINT
            session.execute(text("UPDATE account SET balance = balance + 100 WHERE id = 2"))
            raise RuntimeError("부가 작업 실패")
    except RuntimeError:
        pass                                                     # SAVEPOINT 까지만 롤백되고 바깥 트랜잭션은 살아 있음
print(f"  결과: {balances()}   ← 바깥의 출금(-100)은 커밋되고 안쪽의 입금(+100)만 취소됨")
reset()
