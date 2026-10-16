"""데모 3 : 블로킹 소켓 서버

요청 안에서 2초 기다리는 아주 단순한 서버.
  python 03_blocking_server.py single       # 단일 스레드 : 요청이 줄을 선다
  python 03_blocking_server.py threadpool   # 스레드풀     : 동시에 처리한다
다른 터미널에서 : python 03_client.py 5
"""
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HOST, PORT = "127.0.0.1", 9000
WORK_SECONDS = 2


def handle(conn):
    with conn:
        conn.recv(4096)  # 요청 읽기
        time.sleep(WORK_SECONDS)  # DB / 외부 API 호출을 흉내 : 이 동안 이 스레드는 아무것도 못 한다
        body = f"done by {threading.current_thread().name}\n".encode()
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)


def main(mode):
    pool = ThreadPoolExecutor(max_workers=10) if mode == "threadpool" else None
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"[{mode}] listening on {HOST}:{PORT}")
        while True:
            conn, _ = server.accept()
            if pool:
                pool.submit(handle, conn)  # 다른 스레드에게 넘기고 바로 다음 accept
            else:
                handle(conn)  # 여기서 2초 동안 accept 로 못 돌아간다


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "single")
