"""데모 2-A : select 로 만드는 미니 이벤트루프 (스레드 1개로 여러 연결 처리)

소켓 여러 개를 selectors(커널의 epoll/kqueue 위)에 맡겨 놓고, 준비된 것만 처리한다.
  python 02_selector_loop.py
  python load.py /health 5 8002      # 연결 여러 개를 스레드 없이 처리
  python load.py /report 3 8002      # 콜백 안에서 boto3 를 부르면? -> 루프 전체가 멈춘다
"""
import json
import selectors
import socket

from common import read_report

HOST, PORT = "127.0.0.1", 8002
sel = selectors.DefaultSelector()


def accept(server):
    conn, _ = server.accept()
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, read)  # "읽을 게 오면 read 를 불러 줘"


def read(conn):
    data = conn.recv(4096)
    if data:
        path = data.split(b" ")[1].decode().split("?")[0]
        if path == "/report":
            body = json.dumps({"bytes": read_report()}).encode()  # 블로킹 호출 : 이 스레드가 곧 루프다
        else:
            body = b'{"ok": true}'
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
    sel.unregister(conn)
    conn.close()


server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(128)
server.setblocking(False)
sel.register(server, selectors.EVENT_READ, accept)

print(f"[selector 이벤트루프, 스레드 1개] http://{HOST}:{PORT}")
while True:
    for key, _ in sel.select():  # 준비된 소켓이 생길 때까지 여기서 잠든다 (커널의 대기 큐)
        key.data(key.fileobj)     # 등록해 둔 콜백 호출
