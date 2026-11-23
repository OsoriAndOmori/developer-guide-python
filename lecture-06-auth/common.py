"""공통: Keycloak 주소, 토큰 디코딩 도우미"""
import base64
import json
import time

KC = "http://localhost:8083"
REALM = "lecture"
ISSUER = f"{KC}/realms/{REALM}"
OIDC = f"{ISSUER}/protocol/openid-connect"
DISCOVERY = f"{ISSUER}/.well-known/openid-configuration"

WEB_APP = ("web-app", "web-app-secret")        # (client_id, client_secret)
BATCH_JOB = ("batch-job", "batch-job-secret")
REDIRECT_URI = "http://localhost:8010/callback"


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def decode_jwt(token: str):
    """JWT = header.payload.signature  (앞 둘은 그냥 base64 JSON. 서명 검증은 하지 않는다)"""
    h, p, s = token.split(".")
    return json.loads(b64url_decode(h)), json.loads(b64url_decode(p)), s


def show_claims(token: str, *keys):
    header, payload, sig = decode_jwt(token)
    print("  header :", header)
    for k in keys or payload.keys():
        if k in payload:
            v = payload[k]
            if k in ("exp", "iat", "auth_time") and isinstance(v, int):
                v = f"{v}  ({time.strftime('%H:%M:%S', time.localtime(v))})"
            print(f"  {k:<18}: {v}")
    print(f"  signature         : {sig[:24]}...  (서버만 만들 수 있는 서명)")


# ── 브라우저 없이 Authorization Code 흐름을 그대로 따라가는 도우미 ─────────────
import re
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


def login_steps(username: str, password: str, verbose: bool = False, client=WEB_APP):
    """브라우저가 하는 일을 httpx 로 흉내낸다. 반환: (토큰 응답 dict, 받은 code)"""
    say = print if verbose else (lambda *a, **k: None)
    state = secrets.token_urlsafe(8)
    with httpx.Client(follow_redirects=False) as http:
        params = {"client_id": client[0], "redirect_uri": REDIRECT_URI, "response_type": "code",
                  "scope": "openid", "state": state}
        say(f"\n[1] 브라우저 -> 인증 서버  GET {OIDC}/auth?" + urlencode(params))
        r = http.get(f"{OIDC}/auth", params=params)
        action = re.search(r'action="([^"]+)"', r.text).group(1).replace("&amp;", "&")
        say(f"    <- {r.status_code} 로그인 화면(HTML). 여기서 사용자가 ID/PW 를 입력한다")

        say(f"\n[2] 브라우저 -> 인증 서버  POST 로그인 폼 (username={username}, password=****)")
        # Keycloak 쿠키는 Secure 속성이 붙어 있어 httpx 가 http 로는 안 보낸다. (Chrome 은 localhost 를 예외로 취급)
        cookie = "; ".join(f"{c.name}={c.value}" for c in http.cookies.jar)
        r = http.post(action, data={"username": username, "password": password}, headers={"Cookie": cookie})
        location = r.headers["location"]
        say(f"    <- {r.status_code} Location: {location}")
        q = parse_qs(urlparse(location).query)
        code = q["code"][0]
        assert q["state"][0] == state, "state 불일치 (CSRF 의심)"
        say(f"    code={code[:20]}...   state 확인 OK")

        say(f"\n[3] 브라우저 -> 내 서버  GET {REDIRECT_URI}?code=...&state=...   (여기서부터 내 서버가 일한다)")
        say(f"\n[4] 내 서버 -> 인증 서버  POST {OIDC}/token  (grant_type=authorization_code, code, client_secret)")
        r = http.post(f"{OIDC}/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
            "client_id": client[0], "client_secret": client[1]})
        r.raise_for_status()
        say(f"    <- {r.status_code} " + str({k: (v[:20] + "...") if isinstance(v, str) and len(v) > 40 else v
                                              for k, v in r.json().items()}))
        return r.json(), code
