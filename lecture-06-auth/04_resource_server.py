"""실습 4 : 리소스 서버(우리 API)는 토큰을 어떻게 검증하나

인증 서버에 매번 묻지 않는다. 시작할 때 받아둔 공개키(JWKS)로 '서명, 발급자(iss), 만료(exp)'를 직접 확인하고,
토큰 안의 역할(realm_access.roles)로 인가를 판단한다.

  /public  : 토큰 필요 없음
  /me      : 유효한 토큰이면 누구나
  /admin   : admin 역할이 있어야 함 (없으면 403)

실행: uvicorn 04_resource_server:app --port 8011
"""
import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common import ISSUER, OIDC

app = FastAPI()
bearer = HTTPBearer(auto_error=False)
jwks = jwt.PyJWKClient(f"{OIDC}/certs")          # 공개키를 받아 캐시한다 (kid 로 알맞은 키를 고른다)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(401, "토큰이 없습니다")                       # 401 = 누군지 모르겠다
    try:
        key = jwks.get_signing_key_from_jwt(cred.credentials).key
        return jwt.decode(cred.credentials, key, algorithms=["RS256"], issuer=ISSUER,
                          options={"verify_aud": False})                 # 서명 + iss + exp 검증
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "토큰이 만료되었습니다")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"유효하지 않은 토큰: {e}")


def require_role(role: str):
    def check(user: dict = Depends(current_user)) -> dict:
        if role not in user.get("realm_access", {}).get("roles", []):
            raise HTTPException(403, f"'{role}' 역할이 필요합니다")       # 403 = 누군지는 알지만 권한이 없다
        return user
    return check


@app.get("/public")
def public():
    return {"msg": "누구나"}


@app.get("/me")
def me(user: dict = Depends(current_user)):
    return {"username": user.get("preferred_username"), "sub": user["sub"],
            "roles": user.get("realm_access", {}).get("roles", [])}


@app.get("/admin")
def admin(user: dict = Depends(require_role("admin"))):
    return {"msg": f"관리자 화면입니다, {user.get('preferred_username')}"}
