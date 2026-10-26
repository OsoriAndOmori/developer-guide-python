# 4강. 서버를 직접 만들며 배우기 : WSGI -> ASGI -> FastAPI

블로그 [내 맘대로 Python FastAPI](https://osoriandomori.github.io/posts/%EB%82%B4-%EB%A7%98%EB%8C%80%EB%A1%9C-%EB%8D%B0%EC%9D%B4%ED%84%B0%ED%8C%80-%EA%B3%B5%EB%B6%80-%EB%A3%A8%ED%8A%B8/) 2장의 데모.
LocalStack(S3)에 실제 `boto3` 로 요청을 보내는 서버를 만들어, 서버 구조에 따라 같은 요청이 어떻게 처리되는지 본다.

## 준비

```bash
cd lecture-04-python-servers
docker compose up -d                       # LocalStack(S3) + S3 웹 화면 실행 (이미지를 처음 받을 때만 오래 걸림)
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt            # aioboto3 가 boto3 버전을 바꿀 수 있다
python 00_seed.py                          # 버킷을 만들고 읽을 파일(1MB)을 올림
python common.py                           # read_report() 가 약 0.5초 걸리는지 확인
# S3 웹 화면 : http://localhost:8081  (버킷 lecture04 > reports > report.bin 이 보이면 정상)
# 끝나면: docker compose down
```

- `common.py` 의 `read_report()` 는 S3 에서 파일을 읽는 **동기(블로킹) boto3 호출**이다.
- LocalStack 은 내 컴퓨터 안이라 너무 빨라서, 원격 S3 의 네트워크 왕복을 흉내 내려고 호출마다 **0.5초를 기다리게** 했다(`NETWORK_LATENCY`). 기다리는 동안 스레드가 잠드는 건 진짜 네트워크 대기와 같다.
- 모든 데모의 부하 클라이언트는 `load.py <경로> <요청 수> <포트>`. 요청 N개를 동시에 보내고, 0.3초 뒤 `/health` 도 한 번 불러서 **다른 요청까지 같이 막히는지** 본다.

## 2-1. WSGI 서버 만들기 (스레드풀)

| 파일 | 설명 |
|---|---|
| `wsgi_app.py` | `app(environ, start_response)` 라는 WSGI 앱. `/report` 는 boto3 로 S3 를 읽고, `/sleep?seconds=1` 은 boto3 없이 그 초만큼 쉬고 응답 (`curl "http://127.0.0.1:8001/sleep?seconds=1"`) |
| `01_mini_wsgi_server.py` | 소켓 + HTTP 파싱 + WSGI 앱 호출까지 직접 만든 서버. `single` 또는 `threadpool N` |

```bash
# 터미널 A : 서버                                   터미널 B : 부하 (서버를 바꿀 때마다 A 를 껐다 켠다)
python 01_mini_wsgi_server.py single                python load.py /report 3
python 01_mini_wsgi_server.py threadpool 2          python load.py /report 4
gunicorn wsgi_app:app --threads 4 --bind 127.0.0.1:8001   # 같은 앱을 진짜 WSGI 서버로
```

| 결과(이 컴퓨터) | |
|---|---|
| single, 요청 3개 | 0.6, 1.1, 1.6초에 차례로. `/health` 도 1.6초 |
| 스레드풀 2개, 요청 4개 | 2개씩 0.6초, 1.1초 (스레드 고갈) |

> **브라우저로 테스트할 때 주의** : 브라우저는 **똑같은 URL 의 요청을 하나씩 차례로** 보내는 경우가 있다(HTTP 캐시 때문에 앞 요청이 끝나길 기다림).
> 탭 두 개에서 `/sleep?seconds=10` 을 똑같이 열면 서버에는 요청이 **하나씩** 가서 `/health` 가 막히지 않는다.
> URL 을 다르게(`/sleep?seconds=10&n=1`, `/sleep?seconds=10&n=2`) 하거나 `curl` 로 하면 의도대로 막힌다.
> (이 컴퓨터의 브라우저에서 같은 URL 두 개는 4.0초, 8.0초에 끝났고 `/health` 는 0.5초에 응답. URL 을 다르게 하면 둘 다 4.0초에 끝나고 `/health` 도 4.0초에 응답)

## 2-2. ASGI 서버 만들기 (이벤트루프)

| 파일 | 설명 |
|---|---|
| `02_selector_loop.py` | `selectors` 로 스레드 1개가 여러 연결 처리. 콜백에서 boto3 를 부르거나 `/sleep?seconds=5` 로 쉬면 루프가 막히는 것도 확인 |
| `03_asyncio_server.py` | asyncio 서버. `time.sleep` vs `asyncio.sleep`, boto3 직접 호출 vs `to_thread` |
| `mini_framework.py`, `mini_app.py` | 미니 FastAPI(라우터 데코레이터 + 타입 힌트로 파라미터 주입)와 그 앱 |
| `04_mini_asgi_server.py` | `app(scope, receive, send)` 를 호출하는 ASGI 서버(uvicorn 의 축소판) |

```bash
# 각각 터미널 A 에서 서버를 띄우고, 터미널 B 에서 부하를 준다
python 02_selector_loop.py       # B: python load.py /health 5 8002 ,  python load.py /report 3 8002
python 03_asyncio_server.py      # B: python load.py /sleep-blocking 3 8003   (/sleep-async, /report-blocking, /report-thread)
python 04_mini_asgi_server.py    # B: python load.py /report-blocking 3 8004  (/report, /report-def)
uvicorn mini_app:app --port 8006                                   # 같은 앱을 진짜 uvicorn 으로 (포트 8006)
curl "http://127.0.0.1:8004/add?a=3&b=4"                           # {"sum": 7} : int 로 변환되어 들어옴
```

| 결과(이 컴퓨터) | |
|---|---|
| `/report-blocking` (루프에서 직접 boto3) | 요청 3개 0.5, 1.1, 1.6초 + `/health` 도 1.6초 (루프가 막힘) |
| `/report` (`to_thread`) | 요청 3개 모두 0.6초, `/health` 는 0.3초 |
| 직접 만든 앱을 진짜 uvicorn 으로 | 그대로 동작 |

## 2-3. FastAPI 보기

```bash
python 05_fastapi_app.py            # 포트 8005, 워커를 늘리려면 python 05_fastapi_app.py 4
python load.py /report-async-blocking 3 8005   # async def + boto3 : 막힘
python load.py /report-def 3 8005              # def + boto3      : 스레드풀에서 돌아 안 막힘
python load.py /report-to-thread 3 8005        # async def + to_thread
python load.py /report-aioboto3 3 8005         # async def + 진짜 비동기 boto3(aioboto3)
curl http://127.0.0.1:8005/whoami              # 워커가 여러 개면 PID 가 갈린다
```

| 결과(이 컴퓨터) | |
|---|---|
| `/report-async-blocking` | 0.6, 1.1, 1.6초 + `/health` 도 1.6초 |
| `/report-def`, `/report-to-thread`, `/report-aioboto3` | 모두 0.5~0.6초, `/health` 는 0.3초 |
| 워커 2개, 요청 6번 | PID 가 둘로 갈림(4번 / 2번) |

우리가 만든 조각과의 대응 : `04_mini_asgi_server.py` = **uvicorn**, `mini_framework.py` = **Starlette/FastAPI**,
`mini_framework` 가 `def` 를 `asyncio.to_thread` 로 보내는 부분 = FastAPI 가 `def` 를 스레드풀로 보내는 부분.

## 2-4. 용도에 맞게 서버 고르기 (같은 일, 다른 서버)

요청 수를 늘려서 서버 구조의 차이를 본다.

| 서버와 작업 | 요청 수 | 전체 걸린 시간 |
|---|---|---|
| gunicorn(WSGI) 스레드 4개, boto3 호출 | 40 | 5.4초 |
| FastAPI `def` (스레드풀 40개), boto3 호출 | 40 | 0.8초 |
| FastAPI `async def` + `to_thread`(기본 스레드 수 제한), boto3 호출 | 40 | 1.8초 |
| FastAPI `def` + 0.5초 대기 | 200 | 2.6초 (40개씩 줄 섬) |
| FastAPI `async def` + `asyncio.sleep(0.5)` | 200 | 0.7초 |
| FastAPI `def`, boto3 호출 | 200 | 3.3초 |
| FastAPI `async def` + `to_thread`, boto3 호출 | 200 | 7.3초 (기본 스레드 수 약 18개 제한) |
| FastAPI `async def` + **aioboto3**(진짜 비동기) | 200 | **1.7초** |

- **기다리는 일이 많을수록** 스레드를 한 개씩 점유하는 방식은 스레드 수에서 막히고, 진짜 비동기 대기는 스레드 없이 모두 동시에 기다린다.
- 그래도 boto3 같은 **동기 라이브러리를 쓰는 한** 비동기의 이점은 스레드(풀) 크기 안으로 줄어든다. 200건에서 `def`(스레드 40개)는 3.3초, `to_thread`(기본 스레드 수 제한)는 7.3초, **aioboto3 는 1.7초**였다.
- 다만 aioboto3 도 공짜는 아니다. 요청마다 파이썬 쪽 처리(CPU)가 이벤트루프 스레드 하나에서 일어나서, 대기(0.5초)만 있던 `asyncio.sleep` 실험(0.7초)보다 느리다. 또 **boto3/botocore 버전을 고정**해서 다른 라이브러리와 충돌할 수 있다.
- 동기 라이브러리 중심이고 동시 요청이 수십 개 수준이면 `def` 로 쓰는 선택이 가장 단순하다.
- 숫자는 이 컴퓨터(로컬 LocalStack, 지연 0.5초 흉내) 기준이다. 환경마다 다르니 직접 돌려 본다.
