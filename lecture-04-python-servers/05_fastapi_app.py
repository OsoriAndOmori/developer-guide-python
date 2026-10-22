"""데모 2-D : 진짜 FastAPI (우리가 만든 조각들이 어디에 대응하는지 보기)

  python 05_fastapi_app.py               # 서버 실행 (포트 8005)
  python 05_fastapi_app.py 4             # 워커 4개 (프로세스 4개)
  python load.py /report-async-blocking 3 8005   # async def + boto3 : 서버 전체가 멈춘다
  python load.py /report-def 3 8005              # def + boto3      : 스레드풀에서 돈다
  python load.py /report-to-thread 3 8005        # async def + to_thread
  python load.py /wait-async 200 8005            # 진짜 비동기 대기 : 200개가 0.5초에 끝남
  python load.py /wait-def 200 8005              # 스레드풀이 기다림  : 40개씩 줄을 서서 오래 걸림
  curl http://127.0.0.1:8005/whoami              # 어느 프로세스가 받았나 (워커를 여러 개 띄웠을 때)

대응 관계 :  uvicorn = 우리가 만든 04_mini_asgi_server / FastAPI(Starlette) = mini_framework
"""
import asyncio
import os
import sys
import time

import uvicorn
from fastapi import FastAPI

from common import read_report

app = FastAPI()


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/whoami")
async def whoami():
    return {"pid": os.getpid()}


@app.get("/add")
async def add(a: int, b: int = 10):  # 타입 힌트로 변환되는 것도 FastAPI 가 해 준다
    return {"sum": a + b}


@app.get("/wait-async")
async def wait_async():
    await asyncio.sleep(0.5)  # 순수한 "기다림"(진짜 비동기). 스레드를 쓰지 않고 수천 개도 동시에 기다린다
    return {"waited": 0.5}


@app.get("/wait-def")
def wait_def():
    time.sleep(0.5)  # 같은 기다림을 스레드가 맡으면 : 스레드풀(40개) 크기까지만 동시에 기다린다
    return {"waited": 0.5}


@app.get("/report-async-blocking")
async def report_async_blocking():
    return {"bytes": read_report()}  # 이벤트루프 스레드에서 직접 실행 -> 서버 전체가 멈춘다


@app.get("/report-def")
def report_def():
    return {"bytes": read_report()}  # def -> 스레드풀(기본 40개)에서 실행 -> 다른 요청을 막지 않는다


@app.get("/report-to-thread")
async def report_to_thread():
    return {"bytes": await asyncio.to_thread(read_report)}  # async def 안에서 스레드로 넘기는 방법


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    uvicorn.run("05_fastapi_app:app", host="127.0.0.1", port=8005, workers=workers, log_level="warning")
