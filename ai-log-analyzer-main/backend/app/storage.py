import io
import os
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

load_dotenv("backend/.env")

# Read MinIO config from environment (or defaults for local development)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Create MinIO client
client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)


def ensure_bucket(bucket_name: str):
    """Create bucket if it doesn't exist."""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except S3Error as e:
        raise RuntimeError(f"Failed to ensure bucket: {e}")


def store_log_bytes(data: bytes, key: str, bucket: str = "logs"):
    """
    Store raw log bytes in MinIO.

    Args:
        data: log bytes
        key: object name in bucket (e.g., incident_id.log)
        bucket: bucket name (default: logs)
    """
    ensure_bucket(bucket)

    stream = io.BytesIO(data)
    size = len(data)

    client.put_object(
        bucket_name=bucket,
        object_name=key,
        data=stream,
        length=size,
        content_type="text/plain"
    )

    return {"bucket": bucket, "key": key}


def get_log_bytes(key: str, bucket: str = "logs") -> bytes:
    """
    Retrieve raw log bytes.
    """
    try:
        response = client.get_object(bucket, key)
        content = response.read()
        response.close()
        response.release_conn()
        return content
    except S3Error as e:
        raise RuntimeError(f"MinIO get_object failed: {e}")
