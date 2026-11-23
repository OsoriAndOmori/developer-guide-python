"""실습 1 : 인증 서버는 자기 정보를 스스로 알려준다 (OIDC Discovery + JWKS)

클라이언트/API 가 알아야 하는 주소들(로그인, 토큰, 공개키)을 설정에 하드코딩하지 않고
`.well-known/openid-configuration` 한 곳에서 읽는다. 공개키 목록(JWKS)도 여기서 받는다.

실행: python 01_discover.py        (먼저 docker compose up -d)
"""
import httpx

from common import DISCOVERY

d = httpx.get(DISCOVERY).json()
print("issuer                :", d["issuer"], "  <- 토큰의 iss 값과 같아야 한다")
print("authorization_endpoint:", d["authorization_endpoint"], " (브라우저가 가는 로그인 주소)")
print("token_endpoint        :", d["token_endpoint"], " (내 서버가 code 를 토큰으로 바꾸는 주소)")
print("userinfo_endpoint     :", d["userinfo_endpoint"])
print("jwks_uri              :", d["jwks_uri"], " (토큰 서명을 검증할 공개키)")
print("지원하는 grant_types  :", d["grant_types_supported"])

keys = httpx.get(d["jwks_uri"]).json()["keys"]
print(f"\n공개키 {len(keys)}개")
for k in keys:
    print(f"  kid={k['kid'][:16]}...  alg={k['alg']}  use={k['use']}  kty={k['kty']}")
print("-> API 서버는 이 공개키로 '서명'만 확인하면 된다. 인증 서버에 매 요청마다 물어보지 않는다.")
