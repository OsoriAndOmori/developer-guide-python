"""모든 데모가 같이 쓰는 boto3 설정과 "느린 일" 하나.

LocalStack(S3)에 있는 리포트 파일을 읽어 오는 일을 한다. 실제 서비스에서
"외부 시스템을 호출하고 응답을 기다리는 일"을 대신한다.

LocalStack 은 내 컴퓨터 안이라 응답이 너무 빠르다. 원격 S3 를 부를 때의 네트워크 왕복을
흉내 내려고 요청마다 NETWORK_LATENCY 초를 기다리게 했다 (boto3 이벤트 훅). 기다리는 동안
스레드가 잠드는 것은 진짜 네트워크 대기와 같은 모양이다.
"""
import time

import boto3
from botocore.config import Config

ENDPOINT = "http://localhost:4566"
BUCKET = "lecture04"
KEY = "reports/report.bin"  # 00_seed.py 가 올려 둔다
SEED_MB = 1
NETWORK_LATENCY = 0.5       # 원격 호출의 왕복 지연을 흉내 낸다 (초)


def s3_client():
    # max_pool_connections 를 명시해 두는 습관 (기본값 10)
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="ap-northeast-2",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(max_pool_connections=50, retries={"max_attempts": 1}),
    )


_client = s3_client()  # 클라이언트는 한 번 만들어서 재사용 (스레드 안전)
_client.meta.events.register(
    "before-call.s3.GetObject", lambda **kwargs: time.sleep(NETWORK_LATENCY)
)  # 요청을 보내기 전에 네트워크 지연만큼 기다린다 (time.sleep 은 GIL 을 놓는다)


def read_report() -> int:
    """S3 에서 파일 하나를 통째로 읽는다. 동기(블로킹) 호출이다. 읽은 바이트 수를 돌려준다."""
    return len(_client.get_object(Bucket=BUCKET, Key=KEY)["Body"].read())


if __name__ == "__main__":
    started = time.perf_counter()
    size = read_report()
    print(f"read_report() : {size / 1024 / 1024:.0f}MB 를 {time.perf_counter() - started:.2f}초에 읽음")
