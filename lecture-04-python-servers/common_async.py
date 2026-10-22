"""진짜 비동기 S3 클라이언트(aioboto3) 버전의 read_report.

common.read_report() 와 같은 일을 하지만 `await` 로 기다린다. 기다리는 동안 스레드가 아니라
이벤트루프가 다른 요청을 처리한다. (네트워크 지연 흉내도 asyncio.sleep 으로 맞췄다)

참고 : aioboto3 는 boto3/botocore 의 버전을 특정 범위로 고정한다. 그래서 boto3 를 함께 쓰는
프로젝트에서는 의존성 충돌이 날 수 있다 (이 repo 에서도 aioboto3 설치 때 boto3 버전이 바뀐다).
"""
import asyncio

import aioboto3

from common import BUCKET, ENDPOINT, KEY, NETWORK_LATENCY


async def _simulate_network_latency(**kwargs):
    await asyncio.sleep(NETWORK_LATENCY)  # time.sleep 이 아니라 asyncio.sleep : 스레드를 붙잡지 않는다


def create_client_context():
    """`async with create_client_context() as s3:` 로 쓴다. 클라이언트는 한 번 만들어 재사용."""
    ctx = aioboto3.Session().client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="ap-northeast-2",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return ctx


def register_latency(s3):
    s3.meta.events.register("before-call.s3.GetObject", _simulate_network_latency)


async def read_report_async(s3) -> int:
    obj = await s3.get_object(Bucket=BUCKET, Key=KEY)
    async with obj["Body"] as stream:
        return len(await stream.read())


if __name__ == "__main__":
    import time

    async def main():
        async with create_client_context() as s3:
            register_latency(s3)
            started = time.perf_counter()
            size = await read_report_async(s3)
            print(f"read_report_async() : {size / 1024 / 1024:.0f}MB 를 {time.perf_counter() - started:.2f}초에 읽음")

    asyncio.run(main())
