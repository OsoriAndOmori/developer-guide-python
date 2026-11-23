# 6강 인증 : OAuth 2.0 / OpenID Connect 를 Keycloak 으로 직접 보기

블로그 공통편 6장(인증)의 Authorization Code 다이어그램을 **실제 인증 서버(Keycloak)** 로 따라가 본다.
Keycloak 은 예시일 뿐, 다른 인증 서버(Okta, Auth0, Cognito …)도 같은 표준을 따른다.

## 준비
```bash
docker compose up -d          # Keycloak (처음 20~40초). realm `lecture` 가 자동으로 만들어진다
./setup_admin.sh              # (선택) 관리 화면 http://localhost:8083 을 브라우저로 열 수 있게 (admin / admin)
pip install -r requirements.txt     # 또는 레포 루트의 .venv 사용
```

| 등장인물 | 값 |
|---|---|
| realm | `lecture` (http://localhost:8083/realms/lecture) |
| 사용자 | `alice/alice` (역할 user), `bob/bob` (역할 user, admin) |
| 클라이언트 `web-app` | 사용자가 로그인하는 우리 앱. secret `web-app-secret`, redirect `http://localhost:8010/*` |
| 클라이언트 `batch-job` | 사용자 없이 서버가 직접 토큰을 받음. secret `batch-job-secret` |

## 실습

| 파일 | 보여주는 것 |
|---|---|
| `01_discover.py` | `.well-known/openid-configuration` 으로 인증 서버가 자기 주소와 공개키(JWKS)를 알려준다 |
| `02_client_credentials.py` | 사용자 없이 서버끼리 토큰 받기 + JWT 를 열어보기 (iss, sub, exp, roles) |
| `03_auth_code_steps.py` | **Authorization Code 흐름을 한 단계씩** (로그인 화면 → 302 + code → 토큰 교환) + id token + refresh + code 재사용 실패 |
| `04_resource_server.py` | 우리 API 가 토큰을 검증하는 법 (공개키로 서명, iss, exp 확인, 역할로 인가) |
| `05_call_api.py` | 토큰에 따라 401 / 403 / 200, 위조한 토큰 거절 |
| `06_web_client.py` | 브라우저로 직접 로그인. 다이어그램의 "내 백엔드 서버" 역할 (state, code 교환, 세션) |

```bash
python 01_discover.py
python 02_client_credentials.py
python 03_auth_code_steps.py
uvicorn 04_resource_server:app --port 8011      # 터미널 1
python 05_call_api.py                           # 터미널 2
uvicorn 06_web_client:app --port 8010           # 터미널 2 대신 : 브라우저 http://localhost:8010 (Chrome)
```

## 실행해서 확인한 결과
- 03 : 로그인 후 302 `Location: .../callback?state=...&code=...` → `/token` 교환 200 → access/id/refresh token.
  access token 5분, refresh 30분. 이미 쓴 code 재교환은 `400 invalid_grant (Code not valid)`, 그 뒤 기존 refresh token 도 `400`
  (코드 재사용을 탈취로 보고 로그인 세션을 폐기).
- 05 :

| 누구 | 경로 | 응답 |
|---|---|---|
| 토큰 없음 | /me | 401 |
| alice (user) | /me | 200 |
| alice (user) | /admin | **403** (누군지는 알지만 권한 없음) |
| bob (admin) | /admin | 200 |
| batch-job (service) | /me | 200 (roles: service) |
| alice 토큰 payload 를 admin 으로 위조 | /admin | **401** Signature verification failed |

## 알아둘 것
- Keycloak 쿠키는 `Secure` 속성이 붙어서, 파이썬 클라이언트(03, 05)는 쿠키를 직접 헤더로 보낸다. 브라우저는 `localhost` 를 예외로 취급해서
  Chrome 은 동작한다 (Safari 는 http 로는 로그인이 안 될 수 있다).
- 이 실습은 개발 모드(`start-dev`) + `sslRequired: none` 이다. **운영에서는 반드시 HTTPS.**
- `04_resource_server.py` 는 audience(`aud`) 검증을 껐다. 운영에서는 이 API 를 위한 audience 를 토큰에 넣고 검증한다.
- 데이터는 컨테이너 안에만 있다. `docker compose down` 하면 로그인 세션은 사라지고, realm 은 다시 올릴 때 import 로 복원된다.
