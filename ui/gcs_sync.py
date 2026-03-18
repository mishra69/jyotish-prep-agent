"""
GCS sync helpers for Cloud Run deployment.
Download db on cold start; upload after consultation completes.
When GCS_BUCKET is unset (local dev), all functions are no-ops.
"""
import os

GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_OBJECT = "jyotish.db"
LOCAL_DB   = "/tmp/jyotish.db"


def download():
    if not GCS_BUCKET:
        return
    import google.cloud.storage as _gcs
    client = _gcs.Client()
    blob = client.bucket(GCS_BUCKET).blob(GCS_OBJECT)
    if blob.exists():
        blob.download_to_filename(LOCAL_DB)


def upload():
    if not GCS_BUCKET or not os.path.exists(LOCAL_DB):
        return
    import google.cloud.storage as _gcs
    client = _gcs.Client()
    client.bucket(GCS_BUCKET).blob(GCS_OBJECT).upload_from_filename(LOCAL_DB)
