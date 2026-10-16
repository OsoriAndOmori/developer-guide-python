"""데모 4 : 이벤트루프

A) 태스크 10개에서 time.sleep(1) vs asyncio.sleep(1)
B) 이벤트루프가 막히면 무슨 일이 생기나 : 100ms 마다 찍는 심박(heartbeat)이 멈춘다

실행: python 04_event_loop.py
"""
import asyncio
import time


async def good():
    await asyncio.sleep(1)  # 양보한다 : 기다리는 동안 다른 태스크가 돈다


async def bad():
    time.sleep(1)  # 양보 못 한다 : 스레드(= 이벤트루프)가 통째로 멈춘다


async def part_a():
    print("== A) 태스크 10개 ==")
    for name, fn in (("asyncio.sleep", good), ("time.sleep   ", bad)):
        started = time.perf_counter()
        await asyncio.gather(*(fn() for _ in range(10)))
        print(f"  {name}  {time.perf_counter() - started:5.1f}초")


async def heartbeat(stop):
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(0.1)
        now = time.perf_counter()
        lag = now - last - 0.1
        flag = "   <-- 이벤트루프가 막혀 있었음!" if lag > 0.05 else ""
        print(f"  heartbeat  지연 {lag * 1000:6.0f}ms{flag}")
        last = now


async def part_b():
    print("\n== B) 심박(heartbeat) 중에 블로킹 호출 ==")
    stop = asyncio.Event()
    hb = asyncio.create_task(heartbeat(stop))
    await asyncio.sleep(0.5)
    print("  --- time.sleep(2) 호출 ---")
    time.sleep(2)
    await asyncio.sleep(0.5)
    stop.set()
    await hb


async def main():
    await part_a()
    await part_b()


if __name__ == "__main__":
    asyncio.run(main())
