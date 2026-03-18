"""
Unit tests for ui/gcs_sync.py — GCS download/upload helpers.
All tests run without real GCS credentials via unittest.mock.
google-cloud-storage need not be installed locally.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub out google.cloud.storage before importing gcs_sync so the module
# loads cleanly even without the package installed locally.
_mock_gcs_module = MagicMock()
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.cloud", MagicMock())
sys.modules.setdefault("google.cloud.storage", _mock_gcs_module)

import ui.gcs_sync as gcs_sync  # noqa: E402  (must come after stub)


class _GcsSyncBase(unittest.TestCase):
    """Helpers shared by upload/download test cases."""

    def _set(self, bucket, local_db):
        """Override module-level vars for the duration of a test."""
        self._orig = (gcs_sync.GCS_BUCKET, gcs_sync.LOCAL_DB)
        gcs_sync.GCS_BUCKET = bucket
        gcs_sync.LOCAL_DB   = local_db

    def _restore(self):
        gcs_sync.GCS_BUCKET, gcs_sync.LOCAL_DB = self._orig

    def _make_client(self, blob_exists=True):
        mock_blob = MagicMock()
        mock_blob.exists.return_value = blob_exists
        mock_bucket_obj = MagicMock()
        mock_bucket_obj.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket_obj
        gcs_sync._gcs.Client.return_value = mock_client
        return mock_client, mock_bucket_obj, mock_blob


class TestGcsUpload(_GcsSyncBase):

    def test_noop_when_bucket_not_set(self):
        self._set("", "/tmp/whatever.db")
        gcs_sync._gcs.Client.reset_mock()
        try:
            gcs_sync.upload()
            gcs_sync._gcs.Client.assert_not_called()
        finally:
            self._restore()

    def test_noop_when_db_missing(self):
        self._set("my-bucket", "/tmp/nonexistent_xyz.db")
        gcs_sync._gcs.Client.reset_mock()
        try:
            gcs_sync.upload()
            gcs_sync._gcs.Client.assert_not_called()
        finally:
            self._restore()

    def test_uploads_to_correct_bucket_and_object(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"fake sqlite db")
            tmp_path = f.name
        self._set("my-bucket", tmp_path)
        mock_client, mock_bucket_obj, mock_blob = self._make_client()
        try:
            gcs_sync.upload()
            mock_client.bucket.assert_called_once_with("my-bucket")
            mock_bucket_obj.blob.assert_called_once_with(gcs_sync.GCS_OBJECT)
            mock_blob.upload_from_filename.assert_called_once_with(tmp_path)
        finally:
            self._restore()
            os.unlink(tmp_path)


class TestGcsDownload(_GcsSyncBase):

    def test_noop_when_bucket_not_set(self):
        self._set("", "/tmp/jyotish.db")
        gcs_sync._gcs.Client.reset_mock()
        try:
            gcs_sync.download()
            gcs_sync._gcs.Client.assert_not_called()
        finally:
            self._restore()

    def test_skips_when_blob_missing(self):
        self._set("my-bucket", "/tmp/jyotish.db")
        mock_client, mock_bucket_obj, mock_blob = self._make_client(blob_exists=False)
        try:
            gcs_sync.download()
            mock_blob.download_to_filename.assert_not_called()
        finally:
            self._restore()

    def test_downloads_when_blob_exists(self):
        self._set("my-bucket", "/tmp/jyotish.db")
        mock_client, mock_bucket_obj, mock_blob = self._make_client(blob_exists=True)
        try:
            gcs_sync.download()
            mock_blob.download_to_filename.assert_called_once_with("/tmp/jyotish.db")
        finally:
            self._restore()


if __name__ == "__main__":
    unittest.main()
