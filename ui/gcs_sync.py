"""
GCS sync helpers for Cloud Run deployment.
Download db on cold start; upload after consultation completes.
When GCS_BUCKET is unset (local dev), all functions are no-ops.
"""
import logging
import os

log = logging.getLogger(__name__)

GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_OBJECT = "jyotish.db"
LOCAL_DB   = "/tmp/jyotish.db"


def download():
    if not GCS_BUCKET:
        log.info("gcs_sync.download: GCS_BUCKET not set, skipping")
        return
    log.info("gcs_sync.download: bucket=%s object=%s", GCS_BUCKET, GCS_OBJECT)
    import google.cloud.storage as _gcs
    client = _gcs.Client()
    blob = client.bucket(GCS_BUCKET).blob(GCS_OBJECT)
    if blob.exists():
        blob.download_to_filename(LOCAL_DB)
        size = os.path.getsize(LOCAL_DB)
        log.info("gcs_sync.download: downloaded %d bytes to %s", size, LOCAL_DB)
    else:
        log.info("gcs_sync.download: blob does not exist yet, starting fresh")


def upload():
    if not GCS_BUCKET or not os.path.exists(LOCAL_DB):
        log.info("gcs_sync.upload: skipping (bucket=%r, db_exists=%s)",
                 GCS_BUCKET, os.path.exists(LOCAL_DB))
        return
    # SqliteSaver uses WAL mode. Checkpoint before uploading so all pending
    # writes are flushed from the -wal sidecar into the main DB file.
    import sqlite3
    with sqlite3.connect(LOCAL_DB) as _conn:
        result = _conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        log.info("gcs_sync.upload: wal_checkpoint(TRUNCATE) -> busy=%s log=%s checkpointed=%s",
                 result[0], result[1], result[2])
    size = os.path.getsize(LOCAL_DB)
    log.info("gcs_sync.upload: uploading %d bytes from %s", size, LOCAL_DB)
    import google.cloud.storage as _gcs
    client = _gcs.Client()
    client.bucket(GCS_BUCKET).blob(GCS_OBJECT).upload_from_filename(LOCAL_DB)
    log.info("gcs_sync.upload: done")
