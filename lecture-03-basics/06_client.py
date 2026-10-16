"""데모 6 용 클라이언트.

지정한 엔드포인트에 요청 N개를 동시에 보내고, 0.5초 뒤에 /health 도 한 번 호출해서
"다른 요청까지 같이 막히는지" 본다.

실행: python 06_client.py /async-blocking [요청 수, 기본 5]
"""
import asyncio
import sys
import time

import httpx

PATH = sys.argv[1] if len(sys.argv) > 1 else "/async-blocking"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
BASE = "http://127.0.0.1:8000"


async def call(client, path, label, started):
    await client.get(BASE + path)
    print(f"  {label:<10} 응답까지 {time.perf_counter() - started:4.1f}초")


async def main():
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [asyncio.create_task(call(client, PATH, f"요청 {i}", started)) for i in range(N)]
        await asyncio.sleep(0.5)
        tasks.append(asyncio.create_task(call(client, "/health", "/health", started)))
        await asyncio.gather(*tasks)


print(f"{PATH} 에 요청 {N}개 (+ 0.5초 뒤 /health)")
asyncio.run(main())
