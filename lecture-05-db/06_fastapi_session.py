"""실습 6 : FastAPI 에서 요청 단위 트랜잭션 (Depends + yield)

요청이 들어올 때 세션을 하나 만들고, 엔드포인트가 정상 종료되면 커밋, 예외가 나면 롤백한다.
(스프링의 "요청 단위 트랜잭션"과 같은 모양이고, 세션은 요청마다 새로 만든다 : 세션은 스레드 안전하지 않다)

  python 06_fastapi_session.py
  curl localhost:8016/balances
  curl -X POST "localhost:8016/transfer?src=1&dst=2&amount=100"             # 성공 → 커밋
  curl -X POST "localhost:8016/transfer?src=1&dst=2&amount=100&fail=true"   # 중간에 예외 → 롤백 (500)
  curl localhost:8016/pool                                                  # 풀 상태 (빌려 간 연결 수)

엔드포인트를 def 로 쓴 이유 : 동기 드라이버(PyMySQL)라서 스레드풀에서 돌게 하려는 것
(async def 안에서 이 드라이버를 부르면 이벤트루프가 막힌다 → 비동기 드라이버 aiomysql / asyncmy 를 써야 함)
"""
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from common import URL

engine = create_engine(URL, pool_size=5, max_overflow=0, pool_timeout=5)
app = FastAPI()


def get_session():
    with Session(engine) as session:          # 요청마다 새 세션 (연결은 풀에서 빌림)
        try:
            yield session                     # 엔드포인트가 이 세션을 쓴다
            session.commit()                  # 예외 없이 끝났으면 커밋
        except Exception:
            session.rollback()                # 예외가 났으면 롤백
            raise


@app.get("/balances")
def balances(session: Session = Depends(get_session)):
    return [r[0] for r in session.execute(text("SELECT balance FROM account ORDER BY id"))]


@app.post("/transfer")
def transfer(src: int, dst: int, amount: int, fail: bool = False, session: Session = Depends(get_session)):
    session.execute(text("UPDATE account SET balance = balance - :a WHERE id = :i"), {"a": amount, "i": src})
    if fail:
        raise HTTPException(status_code=500, detail="출금 후 입금 전에 실패 → 롤백됨")
    session.execute(text("UPDATE account SET balance = balance + :a WHERE id = :i"), {"a": amount, "i": dst})
    return {"ok": True}


@app.get("/pool")
def pool():
    return {"status": engine.pool.status()}   # Pool size: 5  Connections in pool: n  Current Overflow: ...


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8016, log_level="warning")
