"""데모 5 : 동기/비동기 x 블로킹/논블로킹

1초 걸리는 로컬 서버에 같은 요청 3개를 네 가지 방식으로 보낸다.
걸린 시간(wall)과 CPU 가 일한 시간(cpu)을 같이 보면 차이가 보인다.

                      블로킹                    논블로킹
   동기      1) urllib 로 하나씩        2) 소켓을 계속 들여다봄(polling)
   비동기    4) 스레드 + 콜백           3) asyncio

실행: python 05_sync_async_matrix.py
"""
import asyncio
import socket
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 9100
N = 3
REQUEST = b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"


class SlowHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(1)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), SlowHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()


# 1) 동기 + 블로킹 : 호출하면 끝날 때까지 기다리고, 결과도 내가 직접 받는다
def sync_blocking():
    for _ in range(N):
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/").read()


# 2) 동기 + 논블로킹 : 호출은 바로 돌아오지만 "끝났어?" 를 내가 계속 물어본다
def sync_nonblocking():
    socks = []
    for _ in range(N):
        s = socket.create_connection(("127.0.0.1", PORT))
        s.sendall(REQUEST)
        s.setblocking(False)
        socks.append(s)
    pending = set(socks)
    polls = 0
    while pending:
        for s in list(pending):
            polls += 1
            try:
                if s.recv(4096) == b"":
                    pending.discard(s)
            except BlockingIOError:
                pass  # 아직 안 왔다 : 바로 다시 물어본다
    print(f"      (\"끝났어?\" 를 {polls:,}번 물어봄)")


# 3) 비동기 + 논블로킹 : 기다리는 동안 이벤트루프가 다른 일을 하고, 끝나면 깨워준다
async def one_async():
    reader, writer = await asyncio.open_connection("127.0.0.1", PORT)
    writer.write(REQUEST)
    await writer.drain()
    await reader.read()
    writer.close()


def async_nonblocking():
    async def main():
        await asyncio.gather(*(one_async() for _ in range(N)))
    asyncio.run(main())


# 4) 비동기 + 블로킹 : 결과는 콜백으로 받지만, 일하는 스레드는 각자 막혀 있다
def async_blocking():
    done = threading.Semaphore(0)

    def blocking_call():
        return urllib.request.urlopen(f"http://127.0.0.1:{PORT}/").read()

    def on_done(_future):
        done.release()  # 끝났다는 알림이 콜백으로 온다

    with ThreadPoolExecutor(max_workers=N) as pool:
        for _ in range(N):
            pool.submit(blocking_call).add_done_callback(on_done)
        for _ in range(N):
            done.acquire()


def measure(label, fn):
    wall, cpu = time.perf_counter(), time.process_time()
    fn()
    print(f"  {label:<22} wall {time.perf_counter() - wall:4.1f}초   cpu {time.process_time() - cpu:4.1f}초")


if __name__ == "__main__":
    start_server()
    time.sleep(0.2)
    print(f"1초 걸리는 요청 {N}개")
    measure("1) 동기 + 블로킹", sync_blocking)
    measure("2) 동기 + 논블로킹", sync_nonblocking)
    measure("3) 비동기 + 논블로킹", async_nonblocking)
    measure("4) 비동기 + 블로킹", async_blocking)
