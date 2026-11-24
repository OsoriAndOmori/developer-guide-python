"""실습 3 : Authorization Code 흐름을 블로그 다이어그램 번호 그대로 (소셜 로그인 방식)

세 주체를 모두 진짜로 돌린다.
  브라우저 : 이 스크립트 (httpx 로 흉내)
  내 서버  : 06_my_server.py 를 이 스크립트가 직접 띄운다 (로그는 [내 서버] 로 출력)
  인증 서버: Keycloak (docker compose up -d)

실행: python 03_auth_code_steps.py       (8010 포트가 비어 있어야 함)
"""
import importlib
import re
import threading
import time

import httpx
import uvicorn

from common import decode_jwt, show_claims

my_server = importlib.import_module("06_my_server")
server = uvicorn.Server(uvicorn.Config(my_server.app, port=8010, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.1)

ME = "http://localhost:8010"
print("브라우저 = 이 스크립트 / 내 서버 = localhost:8010 / 인증 서버 = Keycloak localhost:8083\n")

with httpx.Client() as browser, httpx.Client() as kc:
    print("[0] 브라우저 -> 내 서버  GET /login   (\"로그인\" 버튼을 누름)")
    r = browser.get(f"{ME}/login")
    to_kc = r.headers["location"]
    print(f"    <- {r.status_code} Location: {to_kc[:95]}...")

    print("\n[1] 브라우저 -> 인증 서버  (이동한 로그인 화면에서 ID/PW 입력)")
    r = kc.get(to_kc)
    print(f"    <- {r.status_code} 로그인 화면(HTML)")
    action = re.search(r'action="([^"]+)"', r.text).group(1).replace("&amp;", "&")
    cookie = "; ".join(f"{c.name}={c.value}" for c in kc.cookies.jar)   # Secure 쿠키를 http 로 직접 전달 (common.py 참고)
    r = kc.post(action, data={"username": "alice", "password": "alice"}, headers={"Cookie": cookie})
    callback = r.headers["location"]

    print(f"\n[2] 인증 서버 -> 브라우저  302 Location: {callback[:95]}...")

    print("\n[3] 브라우저 -> 내 서버  GET /callback?code=...&state=...   (이 순간부터 내 서버가 일한다)")
    r = browser.get(callback)
    print(f"    <- {r.status_code} Location: {r.headers['location']}")
    set_cookie = next(c for c in r.headers.get_list("set-cookie") if c.startswith("session="))

    print("\n[6 결과] 브라우저가 받은 쿠키")
    print("    ", set_cookie.split(";")[0][:60] + "...   (+ " + ";".join(set_cookie.split(";")[1:]).strip() + ")")
    my_jwt = browser.cookies["session"]
    print("    쿠키 안의 토큰은 인증 서버 것이 아니라 '우리가 만든' JWT :")
    show_claims(my_jwt)
    print("    브라우저가 가진 쿠키 이름들:", [c.name for c in browser.cookies.jar], " <- Keycloak 토큰은 없다")

    print("\n[이후] 브라우저 -> 내 서버  GET /me   (쿠키만 자동으로 따라감)")
    r = browser.get(f"{ME}/me")
    print("    <-", r.status_code, r.json())

    print("\n[위조] 쿠키의 sub 를 다른 사람(1 -> 99)으로 바꿔서 보내면")
    import base64, json
    h, p, s = my_jwt.split(".")
    payload = decode_jwt(my_jwt)[1]
    payload["sub"] = "99"
    forged = ".".join([h, base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode(), s])
    r = httpx.get(f"{ME}/me", headers={"Authorization": f"Bearer {forged}"})
    print("    <-", r.status_code, r.json())

    print("\n[재로그인] 같은 사람이 다시 로그인하면 회원가입은 일어나지 않는다 (로그 참고)")
    to_kc = browser.get(f"{ME}/login").headers["location"]
    r = kc.get(to_kc, headers={"Cookie": cookie})                     # 인증 서버에 로그인 세션이 남아 있어 화면 없이 바로 code 가 온다
    if r.status_code == 302:
        browser.get(r.headers["location"])
    else:
        action = re.search(r'action="([^"]+)"', r.text).group(1).replace("&amp;", "&")
        cookie = "; ".join(f"{c.name}={c.value}" for c in kc.cookies.jar)
        r = kc.post(action, data={"username": "alice", "password": "alice"}, headers={"Cookie": cookie})
        browser.get(r.headers["location"])
