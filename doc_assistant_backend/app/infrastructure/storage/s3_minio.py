import boto3
from botocore.client import Config

from app.core.config import get_settings

settings = get_settings()

def make_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style":"path"}),
        use_ssl=settings.S3_USE_SSL,
        verify=False if not settings.S3_USE_SSL else True,
    )

def presign_post(bucket: str, key: str, max_mb: int = 25):
    s3 = make_s3()
    conditions = [
        ["content-length-range", 1, max_mb * 1024 * 1024],
    ]
    fields = {}
    return s3.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=600
    )

def presign_get(bucket: str, key: str, ttl: int = 300):
    s3 = make_s3()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=ttl
    )

# Export bucket name from settings for convenience
def get_bucket_name() -> str:
    return settings.S3_BUCKET or "docs"
