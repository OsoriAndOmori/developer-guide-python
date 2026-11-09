"""모든 실습이 같이 쓰는 접속 정보와 작은 도우미들."""
import time
from contextlib import contextmanager

import pymysql

HOST, PORT = "127.0.0.1", 3307
USER, PASSWORD, DATABASE = "root", "root", "lecture05"
URL = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"


def connect(autocommit=True, **kwargs):
    """PyMySQL 로 직접 연결한다 (드라이버 수준에서 무슨 일이 일어나는지 보려고 ORM 없이 쓴다)."""
    kwargs.setdefault("cursorclass", pymysql.cursors.DictCursor)   # 행을 딕셔너리로 받는다 (필요하면 바꿀 수 있음)
    return pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, database=DATABASE,
        autocommit=autocommit, **kwargs,
    )


@contextmanager
def timed(label):
    started = time.perf_counter()
    yield
    print(f"  {label:<40} {time.perf_counter() - started:6.3f}초")


def query(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()
