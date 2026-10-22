"""데모 2-B : asyncio 로 만드는 서버 (콜백 대신 async / await)

엔드포인트 4개로 "이벤트루프를 막는 것"과 "막지 않는 것"을 비교한다.
  python 03_asyncio_server.py
  python load.py /sleep-blocking 3 8003   # time.sleep    : 요청이 줄을 서고 /health 도 같이 막힌다
  python load.py /sleep-async 3 8003      # asyncio.sleep : 동시에 끝나고 /health 는 바로 응답
  python load.py /report-blocking 3 8003  # boto3 를 루프에서 직접 : 막힌다
  python load.py /report-thread 3 8003    # asyncio.to_thread 로 스레드에 맡김 : 안 막힌다
"""
import asyncio
import json
import time

from common import read_report

HOST, PORT = "127.0.0.1", 8003


async def route(path):
    if path == "/sleep-blocking":
        time.sleep(0.5)
    elif path == "/sleep-async":
        await asyncio.sleep(0.5)
    elif path == "/report-blocking":
        return {"bytes": read_report()}                         # 이벤트루프 스레드에서 직접 실행
    elif path == "/report-thread":
        return {"bytes": await asyncio.to_thread(read_report)}  # 스레드풀에 맡기고 await
    return {"ok": True}


async def handle(reader, writer):
    head = await reader.readuntil(b"\r\n\r\n")
    path = head.split(b" ")[1].decode().split("?")[0]
    body = json.dumps(await route(path)).encode()
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
    await writer.drain()
    writer.close()


async def main():
    server = await asyncio.start_server(handle, HOST, PORT)
    print(f"[asyncio] http://{HOST}:{PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
