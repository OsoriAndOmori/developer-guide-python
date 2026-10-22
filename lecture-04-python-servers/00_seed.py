"""LocalStack 에 버킷을 만들고 읽을 파일을 올려 둔다. (처음 한 번만)

실행: python 00_seed.py
"""
import os

from botocore.exceptions import ClientError

from common import BUCKET, KEY, SEED_MB, s3_client

s3 = s3_client()
try:
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "ap-northeast-2"})
except ClientError as e:
    if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
        raise
s3.put_object(Bucket=BUCKET, Key=KEY, Body=os.urandom(SEED_MB * 1024 * 1024))
print(f"s3://{BUCKET}/{KEY} 에 {SEED_MB}MB 를 올렸다")
