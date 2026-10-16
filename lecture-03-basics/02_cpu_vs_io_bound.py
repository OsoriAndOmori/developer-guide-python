"""데모 2 : CPU 바운드 vs I/O 바운드

같은 작업 8개를 순차 / 스레드 / 프로세스로 돌려서 시간을 비교한다.
(다른 터미널에서 htop 이나 활동 상태 보기로 코어 사용률을 같이 보면 좋다)

실행: python 02_cpu_vs_io_bound.py
"""
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

N = 8


def cpu_task(_=None):
    total = 0
    for i in range(6_000_000):
        total += i * i
    return total


def io_task(_=None):
    time.sleep(0.5)  # DB 나 네트워크를 기다리는 것과 같다


def run(label, fn, executor_cls=None):
    started = time.perf_counter()
    if executor_cls is None:
        for _ in range(N):
            fn()
    else:
        with executor_cls(max_workers=N) as ex:
            list(ex.map(fn, range(N)))
    print(f"  {label:<8} {time.perf_counter() - started:5.2f}초")


if __name__ == "__main__":
    print(f"== CPU 바운드 (계산) x {N} ==")
    run("순차", cpu_task)
    run("스레드", cpu_task, ThreadPoolExecutor)
    run("프로세스", cpu_task, ProcessPoolExecutor)

    print(f"\n== I/O 바운드 (0.5초 기다림) x {N} ==")
    run("순차", io_task)
    run("스레드", io_task, ThreadPoolExecutor)
    run("프로세스", io_task, ProcessPoolExecutor)
