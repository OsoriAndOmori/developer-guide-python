"""미니 프레임워크로 만든 앱. 직접 만든 서버로도, 진짜 uvicorn 으로도 돈다.

  python 04_mini_asgi_server.py            # 직접 만든 ASGI 서버
  uvicorn mini_app:app --port 8004         # 진짜 uvicorn (같은 앱 그대로)
"""
import asyncio

from common import read_report
from mini_framework import MiniFastAPI

app = MiniFastAPI()


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/add")
async def add(a: int, b: int = 10):  # 타입 힌트(int) 대로 쿼리 문자열이 변환되어 들어온다
    return {"sum": a + b}


@app.get("/report")
async def report():
    return {"bytes": await asyncio.to_thread(read_report)}  # boto3 는 스레드에 맡긴다


@app.get("/report-blocking")
async def report_blocking():
    return {"bytes": read_report()}  # 이벤트루프에서 직접 : 서버 전체가 멈춘다


@app.get("/report-def")
def report_def():
    return {"bytes": read_report()}  # def : 프레임워크가 스레드로 보내 준다
