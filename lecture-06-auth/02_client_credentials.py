"""실습 2 : 사용자 없이 서버끼리 - Client Credentials  + JWT 뜯어보기

사람이 로그인하는 게 아니라 '배치 서버' 같은 클라이언트가 자기 id/secret 으로 토큰을 받는다.
받은 access token 은 JWT : header.payload.signature . 앞 두 덩어리는 그냥 base64 JSON 이다.

실행: python 02_client_credentials.py
"""
import httpx

from common import BATCH_JOB, OIDC, show_claims

r = httpx.post(f"{OIDC}/token", data={
    "grant_type": "client_credentials", "client_id": BATCH_JOB[0], "client_secret": BATCH_JOB[1]})
print("POST /token ->", r.status_code, " 응답 키:", list(r.json().keys()))
tok = r.json()["access_token"]
print("\n[access token 안쪽]")
show_claims(tok, "iss", "sub", "azp", "exp", "iat", "scope", "realm_access", "preferred_username")
print("\n- iss : 누가 발급했나   - sub : 누구의 토큰인가 (여기선 batch-job 의 서비스 계정)")
print("- exp : 만료 시각       - realm_access.roles : 이 주체가 가진 역할 (인가에 쓴다)")
print("- refresh_token 이 없다 : 이 흐름은 필요하면 그냥 다시 받으면 되기 때문")
