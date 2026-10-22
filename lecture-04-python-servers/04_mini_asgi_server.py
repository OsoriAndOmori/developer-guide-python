"""데모 2-C : 직접 만드는 ASGI 서버 (uvicorn 이 하는 일의 축소판)

asyncio 소켓 서버가 HTTP 를 파싱해서 ASGI 앱 app(scope, receive, send) 을 호출한다.
  python 04_mini_asgi_server.py
  python load.py /report 3 8004          # to_thread : 동시에 끝남
  python load.py /report-blocking 3 8004 # 이벤트루프에서 boto3 : 줄을 서고 /health 도 막힘
  python load.py /report-def 3 8004      # def : 프레임워크가 스레드로 보내서 동시에 끝남
  curl "http://127.0.0.1:8004/add?a=3&b=4"
"""
import asyncio

from mini_app import app

HOST, PORT = "127.0.0.1", 8004


async def handle(reader, writer):
    raw = await reader.readuntil(b"\r\n\r\n")
    method, target, _ = raw.decode().split("\r\n")[0].split()
    path, _, query = target.partition("?")
    scope = {"type": "http", "method": method, "path": path, "query_string": query.encode()}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            writer.write(f"HTTP/1.1 {message['status']} OK\r\n".encode())
            for k, v in message["headers"]:
                writer.write(k + b": " + v + b"\r\n")
            writer.write(b"Connection: close\r\n\r\n")
        elif message["type"] == "http.response.body":
            writer.write(message["body"])
            await writer.drain()

    await app(scope, receive, send)  # ASGI 앱 호출 : 서버와 앱 사이의 약속
    writer.close()


async def main():
    server = await asyncio.start_server(handle, HOST, PORT)
    print(f"[mini ASGI 서버] http://{HOST}:{PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
