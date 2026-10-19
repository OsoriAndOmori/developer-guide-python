# 3강. 기초 : 내 코드는 어떻게 실행되나 (데모)

블로그 [내 맘대로 팀 입사 교육과정](https://osoriandomori.github.io/posts/%EB%82%B4-%EB%A7%98%EB%8C%80%EB%A1%9C-%ED%8C%80-%EC%9E%85%EC%82%AC-%EA%B5%90%EC%9C%A1%EA%B3%BC%EC%A0%95/) 3장(기초)을 데모로 보는 코드.
데모마다 **먼저 결과를 예측해 보고** 돌리는 걸 추천한다.

## 준비

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r lecture-03-basics/requirements.txt   # 6번 데모에서만 필요 (1~5번은 표준 라이브러리)
cd lecture-03-basics
```

## 데모

| # | 파일 | 개념 | 실행 | 볼 것 (이 노트북에서 돌린 결과) |
|---|---|---|---|---|
| 1 | `01_process_vs_thread.py` | 프로세스 vs 스레드, 컨텍스트 스위칭 | `python 01_process_vs_thread.py` | 스레드는 변수를 공유해서 부모도 1, 프로세스는 복사본이라 부모는 그대로 1. 스레드 2000개 생성 시 메모리 18MB → 89MB |
| 2 | `02_cpu_vs_io_bound.py` | CPU 바운드 vs I/O 바운드 | `python 02_cpu_vs_io_bound.py` | 계산: 순차 1.28초, 스레드 1.23초, 프로세스 0.39초. 기다림: 순차 4.03초, 스레드 0.51초 |
| 3 | `03_blocking_server.py`, `03_client.py` | 블로킹 서버, 스레드풀 | 터미널 A `python 03_blocking_server.py single`, 터미널 B `python 03_client.py 4` → 서버를 `threadpool` 로 바꿔서 반복 | single 은 2, 4, 6, 8초에 차례로 끝나고, threadpool 은 4개가 모두 2초에 끝남 |
| 4 | `04_event_loop.py` | 이벤트루프, 블로킹 | `python 04_event_loop.py` | `asyncio.sleep` 10개는 1초, `time.sleep` 10개는 10초. 심박 지연이 평소 1ms 인데 블로킹 때 2000ms |
| 5 | `05_sync_async_matrix.py` | 동기/비동기 x 블로킹/논블로킹 | `python 05_sync_async_matrix.py` | 3초 / 1초(cpu 1.0초) / 1초 / 1초. polling 은 "끝났어?" 를 170만 번 묻느라 CPU 를 씀 |
| 6 | `06_server.py`, `06_client.py` | FastAPI 에서 `def` vs `async def` | 터미널 A `python 06_server.py`, 터미널 B `python 06_client.py /async-blocking` (`/sync-blocking`, `/async-nonblocking` 도) | async-blocking 은 요청 5개가 2, 4, 6, 8, 10초에 끝나고 `/health` 도 10초 뒤에 응답. 나머지 둘은 2초에 끝나고 `/health` 는 0.5초에 응답 |
| 7 | `07_bytecode.py` | 내 코드를 CPU 는 어떻게 알아들을까 (바이트코드, ISA) | `python 07_bytecode.py` | `c = a + b` 가 바이트코드 6줄로 쪼개짐. `uname -m` 이 arm64, `/bin/ls` 는 x86_64 와 arm64e 가 같이 든 universal binary. 반복문 합계 0.18초 vs 내장 `sum()` 0.04초 |

## 진행 팁

- 터미널을 둘로 나눠서 서버 / 클라이언트를 같이 보여 주고, 옆에 `htop`(또는 활동 상태 보기)을 켜 두면 "기다리는 동안 CPU 는 놀고 있다"가 보인다.
- 2번은 htop 의 코어별 사용률을 같이 보면 스레드는 한 코어, 프로세스는 여러 코어를 쓰는 게 보인다.
- 결과 숫자는 환경에 따라 다르니 미리 한 번 돌려서 캡처해 두면 좋다.
- 6번의 `time.sleep(2)` 자리에 `boto3` 같은 동기 라이브러리 호출이 온다고 생각하면 된다.
