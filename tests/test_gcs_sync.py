"""
Unit tests for ui/gcs_sync.py — GCS download/upload helpers.
All tests run without real GCS credentials via unittest.mock.
google-cloud-storage need not be installed locally.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub google.cloud.storage in sys.modules so the lazy import inside
# gcs_sync functions resolves to our mock without the package installed.
_mock_gcs = MagicMock()
sys.modules["google"] = MagicMock(cloud=MagicMock(storage=_mock_gcs))
sys.modules["google.cloud"] = MagicMock(storage=_mock_gcs)
sys.modules["google.cloud.storage"] = _mock_gcs

import ui.gcs_sync as gcs_sync  # noqa: E402


class _Base(unittest.TestCase):

    def setUp(self):
        self._orig = (gcs_sync.GCS_BUCKET, gcs_sync.LOCAL_DB)
        _mock_gcs.reset_mock()

    def tearDown(self):
        gcs_sync.GCS_BUCKET, gcs_sync.LOCAL_DB = self._orig

    def _configure(self, bucket, local_db):
        gcs_sync.GCS_BUCKET = bucket
        gcs_sync.LOCAL_DB   = local_db

    def _make_client(self, blob_exists=True):
        mock_blob = MagicMock()
        mock_blob.exists.return_value = blob_exists
        mock_bucket_obj = MagicMock(blob=MagicMock(return_value=mock_blob))
        mock_client = MagicMock(bucket=MagicMock(return_value=mock_bucket_obj))
        _mock_gcs.Client.return_value = mock_client
        return mock_client, mock_bucket_obj, mock_blob


class TestUpload(_Base):

    def test_noop_when_bucket_not_set(self):
        self._configure("", "/tmp/whatever.db")
        gcs_sync.upload()
        _mock_gcs.Client.assert_not_called()

    def test_noop_when_db_missing(self):
        self._configure("my-bucket", "/tmp/nonexistent_xyz.db")
        gcs_sync.upload()
        _mock_gcs.Client.assert_not_called()

    def test_uploads_to_correct_bucket_and_object(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"fake sqlite db")
            tmp_path = f.name
        try:
            self._configure("my-bucket", tmp_path)
            mock_client, mock_bucket_obj, mock_blob = self._make_client()
            gcs_sync.upload()
            mock_client.bucket.assert_called_once_with("my-bucket")
            mock_bucket_obj.blob.assert_called_once_with(gcs_sync.GCS_OBJECT)
            mock_blob.upload_from_filename.assert_called_once_with(tmp_path)
        finally:
            os.unlink(tmp_path)


class TestDownload(_Base):

    def test_noop_when_bucket_not_set(self):
        self._configure("", "/tmp/jyotish.db")
        gcs_sync.download()
        _mock_gcs.Client.assert_not_called()

    def test_skips_when_blob_missing(self):
        self._configure("my-bucket", "/tmp/jyotish.db")
        mock_client, mock_bucket_obj, mock_blob = self._make_client(blob_exists=False)
        gcs_sync.download()
        mock_blob.download_to_filename.assert_not_called()

    def test_downloads_when_blob_exists(self):
        self._configure("my-bucket", "/tmp/jyotish.db")
        mock_client, mock_bucket_obj, mock_blob = self._make_client(blob_exists=True)
        gcs_sync.download()
        mock_blob.download_to_filename.assert_called_once_with("/tmp/jyotish.db")


if __name__ == "__main__":
    unittest.main()
