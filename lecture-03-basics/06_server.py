"""데모 6 : FastAPI 에서 async def 안에서 블로킹 호출을 하면?

  python 06_server.py                 # 서버 실행 (포트 8000)
  python 06_client.py /async-blocking # 다른 터미널에서
  python 06_client.py /sync-blocking
  python 06_client.py /async-nonblocking

실제 서비스에서는 time.sleep(2) 자리에 boto3 호출 같은 동기 라이브러리가 온다고 생각하면 된다.
"""
import asyncio
import time

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/async-blocking")
async def async_blocking():
    time.sleep(2)  # 이벤트루프 스레드에서 직접 실행 -> 서버 전체가 2초 멈춘다
    return {"endpoint": "async def + time.sleep"}


@app.get("/sync-blocking")
def sync_blocking():
    time.sleep(2)  # def 는 스레드풀(기본 40개)에서 실행 -> 다른 요청은 계속 받는다
    return {"endpoint": "def + time.sleep"}


@app.get("/async-nonblocking")
async def async_nonblocking():
    await asyncio.sleep(2)  # 기다리는 동안 이벤트루프가 다른 요청을 처리한다
    return {"endpoint": "async def + asyncio.sleep"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
