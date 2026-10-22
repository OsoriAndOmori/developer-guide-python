"""서버 데모 공통 부하 클라이언트 : 요청 N개를 동시에 보내고, 0.3초 뒤 /health 도 한 번 호출한다.

실행: python load.py /report 4 [포트, 기본 8001]
"""
import sys
import threading
import time
import urllib.request

PATH = sys.argv[1] if len(sys.argv) > 1 else "/report"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 4
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8001
started = time.perf_counter()


def call(path, label):
    urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=120).read()
    print(f"  {label:<10} 응답까지 {time.perf_counter() - started:4.1f}초")


threads = [threading.Thread(target=call, args=(PATH, f"요청 {i}")) for i in range(N)]
print(f"{PATH} 에 요청 {N}개 (+ 0.3초 뒤 /health)")
for t in threads:
    t.start()
time.sleep(0.3)
health = threading.Thread(target=call, args=("/health", "/health"))
health.start()
for t in threads + [health]:
    t.join()
print(f"  -> 전체 {time.perf_counter() - started:.1f}초")
