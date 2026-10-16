"""데모 1 : 프로세스 vs 스레드, 컨텍스트 스위칭

A) 같은 변수를 스레드는 공유하고, 프로세스는 공유하지 않는다
B) 스레드를 많이 만들면 비용이 든다

실행: python 01_process_vs_thread.py [스레드 수, 기본 2000]
"""
import multiprocessing
import os
import resource
import sys
import threading
import time

shared = {"count": 0}


def add_one():
    shared["count"] += 1
    print(f"  [pid={os.getpid()} thread={threading.current_thread().name}] count={shared['count']}")


def demo_memory():
    print("== A) 메모리 공유 ==")
    print(f"  부모 pid={os.getpid()}, 시작 count={shared['count']}")

    t = threading.Thread(target=add_one, name="worker-thread")
    t.start(); t.join()
    print(f"  스레드 실행 후 부모가 보는 count = {shared['count']}   <- 공유되어서 1")

    ctx = multiprocessing.get_context("fork")  # fork 면 부모 메모리를 복사해서 시작
    p = ctx.Process(target=add_one)
    p.start(); p.join()
    print(f"  프로세스 실행 후 부모가 보는 count = {shared['count']}   <- 복사본만 바뀌어서 그대로 1")


def rss_mb():
    # macOS 는 byte, Linux 는 KB 단위
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1024 / 1024 if sys.platform == "darwin" else r / 1024


def demo_many_threads(n):
    print(f"\n== B) 스레드 {n}개 만들기 ==")
    before = rss_mb()
    stop = threading.Event()
    started = time.perf_counter()
    threads = [threading.Thread(target=stop.wait) for _ in range(n)]
    for t in threads:
        t.start()
    elapsed = time.perf_counter() - started
    print(f"  생성에 {elapsed:.2f}초, 메모리 {before:.0f}MB -> {rss_mb():.0f}MB, 활성 스레드 {threading.active_count()}개")
    stop.set()
    for t in threads:
        t.join()


if __name__ == "__main__":
    demo_memory()
    demo_many_threads(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)
