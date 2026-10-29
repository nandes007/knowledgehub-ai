"""Uploaded files: S3 when S3_BUCKET is set, local disk otherwise (dev and tests).

The returned location is stored in Document.file_path - an s3:// URI or a plain
path - so rows written before the switch to S3 keep working.
"""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from app.config import settings

_S3_SCHEME = "s3://"


@lru_cache
def _s3():
    import boto3

    # Explicit, because pydantic-settings reads .env into `settings`, not os.environ.
    return boto3.client(
        "s3",
        region_name=settings.aws_region or None,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def _bucket_and_key(uri: str) -> tuple[str, str]:
    bucket, _, key = uri.removeprefix(_S3_SCHEME).partition("/")
    return bucket, key


def save(name: str, contents: bytes) -> str:
    if settings.s3_bucket:
        key = f"{settings.s3_prefix}{name}"
        _s3().put_object(Bucket=settings.s3_bucket, Key=key, Body=contents)
        return f"{_S3_SCHEME}{settings.s3_bucket}/{key}"

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / name
    path.write_bytes(contents)
    return str(path)


@contextmanager
def local_copy(location: str) -> Iterator[Path]:
    """Yield a local path to the file; S3 objects are downloaded to a temp dir."""
    if not location.startswith(_S3_SCHEME):
        yield Path(location)
        return

    bucket, key = _bucket_and_key(location)
    with tempfile.TemporaryDirectory() as tmp:
        # Keep the filename: the converter picks a parser by extension.
        path = Path(tmp) / Path(key).name
        _s3().download_file(bucket, key, str(path))
        yield path


def delete(location: str) -> None:
    if location.startswith(_S3_SCHEME):
        bucket, key = _bucket_and_key(location)
        _s3().delete_object(Bucket=bucket, Key=key)
    else:
        Path(location).unlink(missing_ok=True)
