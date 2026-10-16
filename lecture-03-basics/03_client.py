"""데모 3 용 클라이언트 : 동시에 N개 요청을 보내고 각각 몇 초 만에 끝났는지 본다.

실행: python 03_client.py [요청 수, 기본 5] [포트, 기본 9000]
"""
import socket
import sys
import threading
import time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
started = time.perf_counter()


def call(i):
    with socket.create_connection(("127.0.0.1", PORT)) as s:
        s.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        data = b""
        while chunk := s.recv(4096):
            data += chunk
    print(f"요청 {i} 완료: {time.perf_counter() - started:4.1f}초  ({data.splitlines()[-1].decode()})")


threads = [threading.Thread(target=call, args=(i,)) for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join()
