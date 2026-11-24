"""실습 7 : 인증 서버 토큰 뜯어보기 - id token, refresh, code 재사용

03 은 소셜 로그인 형태라 인증 서버 토큰을 서버가 쓰고 버린다. 여기서는 그 토큰들을 직접 받아서
  - access token 과 id token 은 무엇이 다른지
  - refresh token 으로 재로그인 없이 새 access token 을 받는 법
  - 이미 쓴 code 를 다시 쓰면 어떻게 되는지
를 본다. (구글 API 를 사용자 대신 부르려고 구글 토큰을 보관하는 서비스라면 이 토큰들이 보관 대상이다)

실행: python 07_tokens_refresh_reuse.py
"""
import httpx

from common import OIDC, REDIRECT_URI, WEB_APP, login_steps, show_claims

tokens, code = login_steps("alice", "alice", verbose=True)

print("\n[access token] 인증 서버 API / 리소스 서버용. 짧게 산다")
show_claims(tokens["access_token"], "iss", "sub", "azp", "exp", "realm_access", "preferred_username", "scope")
print("\n[id token] '로그인한 사람이 누군지' 알려주는 용도 (OpenID Connect 가 추가). aud 가 우리 client id")
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
    "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
    "client_id": WEB_APP[0], "client_secret": WEB_APP[1]})
print("   ", r.status_code, r.json())
print("    -> code 는 한 번만 쓸 수 있다. 주소창에 노출되는 값이라 그렇게 설계했다")
r = refresh(tokens["refresh_token"])
print("    재사용 시도 뒤 기존 refresh token 도:", r.status_code, r.json())
print("    -> 서버는 code 가 탈취됐다고 보고 그 로그인 세션을 폐기한다 (OAuth 권고 동작)")
