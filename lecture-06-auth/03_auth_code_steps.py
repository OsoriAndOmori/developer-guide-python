"""실습 3 : Authorization Code 흐름을 한 단계씩 (블로그의 시퀀스 다이어그램 그대로)

브라우저가 하는 일(로그인 화면 -> 로그인 -> code 가 붙은 redirect)을 httpx 로 흉내내서
각 단계에서 오가는 HTTP 를 그대로 출력한다. 마지막에 토큰을 뜯어보고, 갱신(refresh)과
code 재사용 실패까지 확인한다.

실행: python 03_auth_code_steps.py
"""
import httpx

from common import OIDC, WEB_APP, login_steps, show_claims

tokens, code = login_steps("alice", "alice", verbose=True)

print("\n[5] access token (API 호출용, 짧게 산다)")
show_claims(tokens["access_token"], "iss", "sub", "azp", "exp", "realm_access", "preferred_username", "scope")
print("\n[5] id token (로그인한 '사람이 누군지' 알려주는 용도 - OpenID Connect 가 추가한 것)")
show_claims(tokens["id_token"], "iss", "aud", "sub", "preferred_username", "email", "name")
print(f"\nexpires_in={tokens['expires_in']}초, refresh_expires_in={tokens['refresh_expires_in']}초")

def refresh(refresh_token):
    return httpx.post(f"{OIDC}/token", data={
        "grant_type": "refresh_token", "refresh_token": refresh_token,
        "client_id": WEB_APP[0], "client_secret": WEB_APP[1]})


print("\n[갱신] refresh token 으로 새 access token 받기 (사용자 재로그인 없음)")
r = refresh(tokens["refresh_token"])
print("   ", r.status_code, "새 access token 앞부분:", r.json()["access_token"][:30], "...")

print("\n[재사용] 이미 쓴 code 로 다시 교환해 보면")
r = httpx.post(f"{OIDC}/token", data={
    "grant_type": "authorization_code", "code": code, "redirect_uri": "http://localhost:8010/callback",
    "client_id": WEB_APP[0], "client_secret": WEB_APP[1]})
print("   ", r.status_code, r.json())
print("    -> code 는 한 번만 쓸 수 있다. 주소창에 노출되는 값이라 그렇게 설계했다")
r = refresh(tokens["refresh_token"])
print("    재사용 시도 뒤 기존 refresh token 도:", r.status_code, r.json())
print("    -> 서버는 code 가 탈취됐다고 보고 그 로그인 세션을 폐기한다 (OAuth 권고 동작)")
