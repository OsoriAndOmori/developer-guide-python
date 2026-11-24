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

## 두 가지 사용 패턴
이 실습은 Keycloak 을 **"구글 같은 외부 인증 서버"** 로 보고 소셜 로그인 방식(패턴 A)을 중심으로 한다. 패턴 B 는 비교용이다.

| | A. 소셜 로그인 방식 (03, 06) | B. 인증 서버 토큰을 그대로 쓰는 방식 (04, 05) |
|---|---|---|
| 인증 서버 토큰 | 서버가 id token 으로 신원만 확인하고 **버린다** | 클라이언트가 들고 API 에 보낸다 |
| 브라우저가 가진 것 | **우리가 발급한 JWT/세션** 쿠키 | 인증 서버의 access token |
| API 가 검증하는 것 | 우리 JWT (우리가 서명) | 인증 서버의 JWT (공개키로 서명 검증) |
| 어울리는 곳 | 구글, 카카오 로그인 | 사내 SSO, 여러 서비스가 같은 인증 서버를 믿는 구조 |

## 블로그 시퀀스 다이어그램과의 대응 (`03_auth_code_steps.py`)

| 다이어그램 | 실습에서 일어나는 일 |
|---|---|
| (0) 블로그에는 없음 | 내 서버 `/login` 이 브라우저를 인증 서버로 302 (client_id, redirect_uri, state) |
| 1. ID/PW 전송 | 로그인 화면을 받고 ID/PW 를 POST |
| 2. 302 `callback?code=` | 인증 서버가 code 가 붙은 redirect 를 준다 |
| 3. `GET /callback?code=` | **실제로** 내 서버(06_my_server.py)가 요청을 받는다 |
| 4. `POST /token` (code + secret) | 내 서버가 인증 서버를 호출 (로그에 `[내 서버]` 로 표시) |
| 5. Access Token 응답 | access / id / refresh token 수신 |
| 4단계 박스: 사용자 조회 / 가입 / 자체 JWT | id token 서명, iss, aud 검증 → 사용자 조회 또는 회원가입 → **우리 JWT** 발급 |
| 6. `Set-Cookie` 에 JWT (A 방식) | `Set-Cookie: session=<우리 JWT>; HttpOnly` |

## 실습

| 파일 | 보여주는 것 |
|---|---|
| `01_discover.py` | `.well-known/openid-configuration` 으로 인증 서버가 자기 주소와 공개키(JWKS)를 알려준다 |
| `02_client_credentials.py` | 사용자 없이 서버끼리 토큰 받기 + JWT 를 열어보기 (iss, sub, exp, roles) |
| `03_auth_code_steps.py` | **블로그 다이어그램 0~6 단계를 진짜 HTTP 로** (내 서버를 스스로 띄움). 자체 JWT 쿠키, 위조 거절, 재로그인 |
| `04_resource_server.py` | (패턴 B) API 가 인증 서버 토큰을 검증하는 법: 공개키로 서명, iss, exp 확인, 역할로 인가 |
| `05_call_api.py` | (패턴 B) 토큰에 따라 401 / 403 / 200, 위조한 토큰 거절 |
| `06_my_server.py` | (패턴 A) 내 백엔드 서버. 브라우저로 직접 로그인해 볼 수 있다 |
| `07_tokens_refresh_reuse.py` | access vs id token, refresh 로 갱신, 이미 쓴 code 재사용 시 실패 |

```bash
python 01_discover.py
python 02_client_credentials.py
python 03_auth_code_steps.py                    # 8010 포트를 쓴다 (06 을 따로 켜 둔 상태면 끌 것)
python 07_tokens_refresh_reuse.py
uvicorn 04_resource_server:app --port 8011      # 터미널 1
python 05_call_api.py                           # 터미널 2
uvicorn 06_my_server:app --port 8010            # 브라우저로 http://localhost:8010 (Chrome)
```

## 실행해서 확인한 결과
- 03 : 쿠키에는 `session`(HS256, `iss=my-service`) 하나뿐이고 Keycloak 토큰은 없다. `/me` 는 200, 쿠키의 `sub` 를 99 로 바꾸면
  `401 Signature verification failed`. 같은 사람이 다시 로그인하면 `기존 사용자` 로 처리된다(처음 한 번만 회원가입).
- 07 : 이미 쓴 code 재교환은 `400 invalid_grant`, 그 뒤 기존 refresh token 도 `400` (코드 재사용을 탈취로 보고 세션 폐기).
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
- Keycloak 쿠키는 `Secure` 속성이 붙어서, 파이썬 클라이언트(03, 05, 07)는 쿠키를 직접 헤더로 보낸다. 브라우저는 `localhost` 를 예외로 취급해서
  Chrome 은 동작한다 (Safari 는 http 로는 로그인이 안 될 수 있다).
- 이 실습은 개발 모드(`start-dev`) + `sslRequired: none` 이다. **운영에서는 반드시 HTTPS.**
- `04_resource_server.py` 는 audience(`aud`) 검증을 껐다. 운영에서는 이 API 를 위한 audience 를 토큰에 넣고 검증한다.
- 06 의 사용자 목록(`users`)은 메모리에 있다. 실서비스는 DB. 우리 JWT 서명키(HS256)도 코드에 박혀 있으니 실서비스에서는 비밀 관리 도구로 뺀다.
  여러 서비스가 우리 JWT 를 검증해야 하면 RS256(공개키 배포)로 한다.
- 구글 API 를 사용자 대신 불러야 해서 인증 서버 토큰을 보관해야 한다면: 서버 DB 에 저장하고 refresh token 은 암호화한다. 브라우저에는 주지 않는다.
- 데이터는 컨테이너 안에만 있다. `docker compose down` 하면 로그인 세션은 사라지고, realm 은 다시 올릴 때 import 로 복원된다.
