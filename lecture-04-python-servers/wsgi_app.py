"""WSGI 앱 : app(environ, start_response) 라는 약속만 지키면 어떤 WSGI 서버에서도 돈다.

Django, Flask 도 결국 이 모양의 함수(app)이고, gunicorn 같은 서버가 이걸 호출한다.
"""
import json
import time
from urllib.parse import parse_qs

from common import read_report


def app(environ, start_response):
    path = environ["PATH_INFO"]
    if path == "/report":
        size = read_report()  # boto3 : 동기(블로킹) 호출. 끝날 때까지 이 스레드는 기다린다
        body = json.dumps({"bytes": size}).encode()
    elif path == "/sleep":
        # boto3 없이 "기다리는 일" 자체만 흉내 낸다. /sleep?seconds=2 (기본 0.5초, 최대 10초)
        seconds = min(float(parse_qs(environ["QUERY_STRING"]).get("seconds", ["0.5"])[0]), 10)
        time.sleep(seconds)
        body = json.dumps({"slept": seconds}).encode()
    elif path == "/health":
        body = b'{"ok": true}'
    else:
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"not found"]
    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]
