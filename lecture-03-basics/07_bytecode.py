"""데모 7 : 내 코드를 CPU 는 어떻게 알아들을까?

A) 파이썬 코드는 바이트코드로 쪼개진다 (dis)
B) 내 컴퓨터는 어떤 ISA(명령어 집합)를 쓰나 (uname, file)
C) 인터프리터 루프의 비용 : 같은 합계를 파이썬 반복문 vs C 로 짠 sum() 으로

실행: python 07_bytecode.py
"""
import dis
import platform
import shutil
import subprocess
import sys
import time


def add(a, b):
    c = a + b
    return c


def part_a():
    print("== A) 바이트코드 : c = a + b 는 이렇게 쪼개진다 ==")
    dis.dis(add)
    n = len(list(dis.get_instructions(add)))
    print(f"\n  함수 하나가 바이트코드 {n}줄. 이 한 줄 한 줄을 C 로 짠 인터프리터가 읽고, 각각이 수십 개의 기계어로 실행된다")
    print("  (바이트코드 이름은 파이썬 버전마다 다르다)")


def part_b():
    print("\n== B) 내 컴퓨터의 ISA ==")
    print(f"  platform.machine() = {platform.machine()}   (arm64 = ARM, x86_64 = 인텔/AMD)")
    print(f"  python 버전 = {sys.version.split()[0]}")
    if shutil.which("file"):
        for target in (sys.executable, "/bin/ls"):
            lines = subprocess.run(["file", "-L", target], capture_output=True, text=True).stdout.strip().splitlines()
            out = lines[0] if lines else ""
            if out:
                print(f"  file {target}\n    -> {out}")
        print("  (universal binary 라고 나오면 한 파일 안에 ISA 별 기계어가 여러 벌 들어 있다는 뜻)")
    print("  아키텍처가 다른 서버로 이미지를 옮기면 'exec format error' 가 난다 : 기계어(ISA) 가 다르기 때문")


def python_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total


def part_c(n=10_000_000):
    print(f"\n== C) 인터프리터의 비용 : 0 부터 {n:,} 미만의 합 ==")
    started = time.perf_counter()
    python_sum(n)
    py = time.perf_counter() - started

    started = time.perf_counter()
    sum(range(n))  # 반복문이 C 로 짠 코드 안에서 돈다
    c = time.perf_counter() - started
    print(f"  파이썬 반복문 {py:5.2f}초")
    print(f"  내장 sum()   {c:5.2f}초   ({py / c:.0f}배 빠름)")
    print("  같은 일인데 바이트코드를 한 줄씩 해석하느냐, 처음부터 기계어(C) 로 도느냐의 차이")


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
