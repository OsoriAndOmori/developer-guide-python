"""실습 6 : 브라우저로 직접 로그인해 보기 - '내 백엔드 서버' 역할 (블로그 다이어그램의 가운데 상자)

  /login     -> 인증 서버(Keycloak) 로그인 화면으로 보낸다 (state 저장)
  /callback  -> code 를 받아 토큰으로 교환한다 (client_secret 은 서버만 안다)
  /          -> 토큰 내용, API 호출 버튼, 갱신, 로그아웃

실행:
  uvicorn 04_resource_server:app --port 8011      (터미널 1 : 우리 API)
  uvicorn 06_web_client:app --port 8010           (터미널 2 : 이 파일)
  브라우저로 http://localhost:8010   (alice/alice 또는 bob/bob. Chrome 권장)
"""
import json
import secrets
from html import escape
from urllib.parse import urlencode

import httpx
from fastapi import Cookie, FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from common import OIDC, REDIRECT_URI, WEB_APP, decode_jwt

API = "http://localhost:8011"
app = FastAPI()
sessions: dict[str, dict] = {}          # sid -> {"state":..., "tokens":...}   (메모리. 실서비스는 Redis 등)


def page(body: str) -> HTMLResponse:
    return HTMLResponse(f"<meta charset=utf-8><body style='font-family:sans-serif;max-width:860px;margin:30px auto'>{body}")


@app.get("/")
def index(sid: str | None = Cookie(None)):
    s = sessions.get(sid or "", {})
    if "tokens" not in s:
        return page("<h2>로그인 전</h2><a href='/login'>로그인 (Keycloak)</a>")
    t = s["tokens"]
    payload = decode_jwt(t["access_token"])[1]
    return page(f"""<h2>로그인됨: {escape(payload.get('preferred_username', '?'))}</h2>
      <p>역할: {payload.get('realm_access', {}).get('roles')}</p>
      <p><a href='/api/me'>API /me</a> | <a href='/api/admin'>API /admin (admin 만)</a> |
         <a href='/refresh'>토큰 갱신</a> | <a href='/logout'>로그아웃</a></p>
      <h3>access token payload</h3><pre>{escape(json.dumps(payload, indent=2, ensure_ascii=False))}</pre>
      <h3>refresh token (앞부분)</h3><pre>{escape(t['refresh_token'][:60])}...</pre>""")


@app.get("/login")
def login():
    sid, state = secrets.token_urlsafe(16), secrets.token_urlsafe(8)
    sessions[sid] = {"state": state}
    q = urlencode({"client_id": WEB_APP[0], "redirect_uri": REDIRECT_URI, "response_type": "code",
                   "scope": "openid", "state": state})
    r = RedirectResponse(f"{OIDC}/auth?{q}")                       # 1. 브라우저를 인증 서버로 보냄
    r.set_cookie("sid", sid, httponly=True, samesite="lax")
    return r


@app.get("/callback")
def callback(code: str, state: str, sid: str | None = Cookie(None)):
    s = sessions.get(sid or "")
    if not s or s.get("state") != state:
        return page("state 가 맞지 않습니다 (CSRF 의심)")
    r = httpx.post(f"{OIDC}/token", data={                          # 4. code -> 토큰 (서버끼리, secret 포함)
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": WEB_APP[0], "client_secret": WEB_APP[1]})
    if r.status_code != 200:
        return page(f"토큰 교환 실패: {escape(r.text)}")
    s["tokens"] = r.json()
    return RedirectResponse("/")


@app.get("/api/{path}")
def call_api(path: str, sid: str | None = Cookie(None)):
    t = sessions.get(sid or "", {}).get("tokens")
    if not t:
        return RedirectResponse("/login")
    r = httpx.get(f"{API}/{path}", headers={"Authorization": f"Bearer {t['access_token']}"})
    return page(f"<h3>GET {API}/{path} -> {r.status_code}</h3><pre>{escape(r.text)}</pre><a href='/'>돌아가기</a>")


@app.get("/refresh")
def refresh(sid: str | None = Cookie(None)):
    s = sessions.get(sid or "", {})
    r = httpx.post(f"{OIDC}/token", data={"grant_type": "refresh_token", "refresh_token": s["tokens"]["refresh_token"],
                                          "client_id": WEB_APP[0], "client_secret": WEB_APP[1]})
    if r.status_code == 200:
        s["tokens"] = r.json()
    return RedirectResponse("/")


@app.get("/logout")
def logout(sid: str | None = Cookie(None)):
    s = sessions.pop(sid or "", {})
    q = urlencode({"client_id": WEB_APP[0], "post_logout_redirect_uri": "http://localhost:8010/",
                   **({"id_token_hint": s["tokens"]["id_token"]} if "tokens" in s else {})})
    return RedirectResponse(f"{OIDC}/logout?{q}")                   # 인증 서버의 로그인 세션도 끝낸다
