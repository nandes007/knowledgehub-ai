from pathlib import Path

from app.config import settings
from app.services import storage


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[(bucket, key)])

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


def test_s3_round_trip(monkeypatch):
    fake = _FakeS3()
    monkeypatch.setattr(storage, "_s3", lambda: fake)
    monkeypatch.setattr(settings, "s3_bucket", "test-bucket")
    monkeypatch.setattr(settings, "s3_prefix", "knowledgehub/")

    location = storage.save("doc-1.md", b"# Hello")
    assert location == "s3://test-bucket/knowledgehub/doc-1.md"

    with storage.local_copy(location) as path:
        assert path.suffix == ".md"
        assert path.read_bytes() == b"# Hello"
    assert not path.exists()

    storage.delete(location)
    assert fake.objects == {}


def test_local_disk_when_no_bucket(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "s3_bucket", "")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    location = storage.save("doc-1.md", b"# Hello")
    with storage.local_copy(location) as path:
        assert path.read_bytes() == b"# Hello"

    storage.delete(location)
    assert not Path(location).exists()
