"""실습 6 : '내 백엔드 서버' - 소셜 로그인처럼 쓰기 (블로그 다이어그램의 가운데 상자)

Keycloak 을 "구글 같은 외부 인증 서버"라고 생각하고 만든다.
  - 인증 서버가 준 토큰(access/refresh)은 사용자에게 주지 않는다.
  - id token 으로 '누구인지'만 확인하고, 우리 서비스의 사용자와 연결(없으면 가입)한 뒤
    **우리가 만든 JWT** 를 Set-Cookie 로 내려준다. 이후엔 이 JWT 로만 통신한다.

  GET /login     0. 브라우저를 인증 서버로 보냄 (client_id, redirect_uri, state)
  GET /callback  3~6. code 받기 -> 토큰 교환 -> id token 검증 -> 사용자 조회/가입 -> 자체 JWT 발급 -> Set-Cookie
  GET /me        우리 JWT 를 검증해서 누구인지 알려줌
  GET /logout    우리 쿠키 삭제

실행: uvicorn 06_my_server:app --port 8010   -> 브라우저 http://localhost:8010 (alice/alice, Chrome 권장)
(03_auth_code_steps.py 는 이 서버를 스스로 띄우니 따로 실행하지 않아도 된다)
"""
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Cookie, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from common import ISSUER, OIDC, REDIRECT_URI, WEB_APP

MY_ISS = "my-service"
# 우리 JWT 서명키. 서버 한 곳만 검증하면 HS256(비밀키), 여러 서비스가 검증하면 RS256(공개키)로 한다.
MY_SECRET = "dev-only-secret-change-me-0123456789"
MY_JWT_TTL = 3600

app = FastAPI()
users: dict[tuple[str, str], dict] = {}          # (인증 서버, sub) -> 우리 서비스의 사용자  (실서비스는 DB)
jwks = jwt.PyJWKClient(f"{OIDC}/certs")


def log(msg: str):
    print(f"      [내 서버] {msg}", flush=True)


@app.get("/")
def index():
    return HTMLResponse("<meta charset=utf-8><a href='/login'>로그인 (Keycloak)</a> | <a href='/me'>/me</a> | "
                        "<a href='/logout'>로그아웃</a>")


@app.get("/login")
def login():
    state = secrets.token_urlsafe(8)
    q = urlencode({"client_id": WEB_APP[0], "redirect_uri": REDIRECT_URI, "response_type": "code",
                   "scope": "openid", "state": state})
    log(f"0. 로그인 시작. state={state} 를 쿠키에 적어두고 브라우저를 인증 서버로 보낸다 (302)")
    r = RedirectResponse(f"{OIDC}/auth?{q}")
    r.set_cookie("oauth_state", state, httponly=True, samesite="lax", max_age=300)
    return r


@app.get("/callback")
def callback(code: str, state: str, oauth_state: str | None = Cookie(None)):
    log(f"3. GET /callback?code={code[:12]}...&state=...   브라우저가 가져온 code 를 받았다")
    if not oauth_state or oauth_state != state:                 # 내가 시작한 로그인인지 확인 (CSRF 방지)
        raise HTTPException(400, "state 가 맞지 않습니다")

    log("4. POST /token  (code + client_secret)   <- secret 은 서버만 알고, 브라우저는 모른다")
    r = httpx.post(f"{OIDC}/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": WEB_APP[0], "client_secret": WEB_APP[1]})
    if r.status_code != 200:
        raise HTTPException(400, f"토큰 교환 실패: {r.text}")
    tokens = r.json()
    log(f"5. 인증 서버 응답: {list(tokens.keys())[:6]} ...")

    # id token = '누가 로그인했나'. 서명, 발급자, 대상(aud)을 확인한다
    key = jwks.get_signing_key_from_jwt(tokens["id_token"]).key
    claims = jwt.decode(tokens["id_token"], key, algorithms=["RS256"], issuer=ISSUER, audience=WEB_APP[0])
    log(f"   id token 검증 OK: sub={claims['sub'][:8]}..., name={claims.get('name')}, email={claims.get('email')}")

    # 우리 서비스의 사용자와 연결 (없으면 회원가입)
    ukey = (ISSUER, claims["sub"])
    if ukey not in users:
        users[ukey] = {"id": len(users) + 1, "name": claims.get("name"), "email": claims.get("email"), "roles": ["user"]}
        log(f"   처음 온 사람이라 회원가입: 우리 사용자 id={users[ukey]['id']}")
    else:
        log(f"   기존 사용자: 우리 사용자 id={users[ukey]['id']}")
    user = users[ukey]

    # 우리 JWT 발급. 인증 서버의 access/refresh token 은 여기서 버린다 (인증 서버 API 를 부를 일이 없으므로)
    now = int(time.time())
    my_jwt = jwt.encode({"iss": MY_ISS, "sub": str(user["id"]), "name": user["name"], "roles": user["roles"],
                         "iat": now, "exp": now + MY_JWT_TTL}, MY_SECRET, algorithm="HS256")
    log("   우리 JWT 발급. 인증 서버 토큰은 저장하지 않고 버린다")

    log("6. 최종 응답: Set-Cookie: session=<우리 JWT>; HttpOnly   (A 방식)")
    resp = RedirectResponse("/me")
    resp.set_cookie("session", my_jwt, httponly=True, samesite="lax", max_age=MY_JWT_TTL)
    resp.delete_cookie("oauth_state")
    return resp


def current_user(session: str | None, authorization: str | None) -> dict:
    token = session or (authorization or "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "로그인이 필요합니다")
    try:
        return jwt.decode(token, MY_SECRET, algorithms=["HS256"], issuer=MY_ISS)
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"유효하지 않은 토큰: {e}")


@app.get("/me")
def me(session: str | None = Cookie(None), authorization: str | None = Header(None)):
    u = current_user(session, authorization)
    return {"id": u["sub"], "name": u["name"], "roles": u["roles"]}


@app.get("/logout")
def logout():
    r = RedirectResponse("/")
    r.delete_cookie("session")
    return r
