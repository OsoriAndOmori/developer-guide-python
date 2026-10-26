"""데모 1 : 직접 만드는 WSGI 서버 (gunicorn 이 하는 일의 축소판)

소켓으로 요청을 받아 HTTP 를 파싱하고, WSGI 앱 app(environ, start_response) 을 호출한다.
  python 01_mini_wsgi_server.py single          # 스레드 1개 : 요청이 줄을 선다
  python 01_mini_wsgi_server.py threadpool 2    # 스레드풀 2개 : 동시에 2개씩
다른 터미널에서 : python load.py /report 4      (요청 4개 + 0.3초 뒤 /health)
                 curl "http://127.0.0.1:8001/sleep?seconds=1"   (boto3 없이 1초 쉬고 응답)

같은 앱을 진짜 WSGI 서버로 돌려 보기 :
  gunicorn wsgi_app:app --threads 4 --bind 127.0.0.1:8001
"""
import io
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

from wsgi_app import app

HOST, PORT = "127.0.0.1", 8001


def parse_request(conn):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        data += chunk
    head = data.split(b"\r\n\r\n", 1)[0].decode()
    request_line, *header_lines = head.split("\r\n")
    method, target, _ = request_line.split()
    path, _, query = target.partition("?")
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
        "SERVER_NAME": HOST, "SERVER_PORT": str(PORT), "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(),
    }
    for line in header_lines:
        name, _, value = line.partition(":")
        environ["HTTP_" + name.strip().upper().replace("-", "_")] = value.strip()
    return environ


def handle(conn):
    with conn:
        environ = parse_request(conn)
        if environ is None:
            return
        captured = {}

        def start_response(status, headers):
            captured["status"], captured["headers"] = status, headers

        body = b"".join(app(environ, start_response))  # 앱 호출 : 여기서 블로킹 호출이 일어난다
        head = f"HTTP/1.1 {captured['status']}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in captured["headers"])
        conn.sendall(head.encode() + b"Connection: close\r\n\r\n" + body)


def main(mode, workers):
    pool = ThreadPoolExecutor(max_workers=workers) if mode == "threadpool" else None
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(128)
        print(f"[{mode}{f' x{workers}' if pool else ''}] http://{HOST}:{PORT}")
        while True:
            conn, _ = server.accept()
            if pool:
                pool.submit(handle, conn)  # 빈 스레드에 던지고 바로 다음 accept
            else:
                handle(conn)               # 이 요청이 끝날 때까지 다음 accept 를 못 한다


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "single", int(sys.argv[2]) if len(sys.argv) > 2 else 4)
