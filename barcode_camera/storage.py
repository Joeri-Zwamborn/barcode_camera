"""Local PNG files are the persistent upload queue."""
import datetime
import hashlib
import logging
import os
import threading
import uuid
from pathlib import Path

import cv2
from azure.core.exceptions import ResourceExistsError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from config import AZURE_ENABLED, LOCAL_SAVE_DIR, AZURE
from barcodes import is_valid_barcode

logger = logging.getLogger(__name__)
RETRY_SECONDS = 30


def save_image(barcode, frame):
    """Return success once the photo is safely saved, without waiting for Azure."""
    if not is_valid_barcode(barcode):
        logger.error("Barcode rejected: use 1–128 ASCII letters/digits, dots, underscores or hyphens, starting with a letter/digit")
        return False
    directory = Path(LOCAL_SAVE_DIR).resolve()
    now = datetime.datetime.now()
    timestamp = str(now).replace(":", "-") if os.name == "nt" else str(now)
    # Unique names also prevent two stations from overwriting the same capture.
    filename = directory / f"{barcode}_{uuid.uuid4().hex}_{timestamp}.png"
    temporary = filename.with_suffix(".pending")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if filename.resolve().parent != directory or temporary.resolve().parent != directory:
            raise ValueError("Photo path is outside the configured image directory")
        success, encoded = cv2.imencode(".png", frame)
        if not success:
            raise RuntimeError("Failed to encode camera image")
        with temporary.open("xb") as image_file:
            image_file.write(encoded.tobytes())
            image_file.flush()
            os.fsync(image_file.fileno())
        # The uploader only sees complete PNGs.
        temporary.replace(filename)
        if os.name == "posix":
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        logger.info("Saved image: %s", filename)
        return True
    except Exception:
        logger.exception("Failed to save image: %s", filename)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to remove incomplete image: %s", temporary)
        return False


def upload_to_azure(filename, service):
    local_file = Path(filename)
    blob = service.get_blob_client(container=AZURE["container"], blob=local_file.name)
    try:
        with local_file.open("rb") as image_file:
            blob.upload_blob(image_file, overwrite=False)
    except ResourceExistsError:
        # A previous attempt may have succeeded before its response was lost.
        # Verify bytes before treating an existing blob as a completed upload.
        local_hash = hashlib.sha256()
        with local_file.open("rb") as image_file:
            for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
                local_hash.update(chunk)
        remote_hash = hashlib.sha256()
        for chunk in blob.download_blob().chunks():
            remote_hash.update(chunk)
        if local_hash.digest() != remote_hash.digest():
            raise RuntimeError(f"Existing Azure blob differs from local photo: {local_file.name}")


def upload_pending_once(stop_event, service):
    """Retry every saved PNG, including photos left by an earlier process."""
    directory = Path(LOCAL_SAVE_DIR)
    for filename in sorted(directory.glob("*.png")):
        if stop_event.is_set():
            break
        try:
            upload_to_azure(filename, service)
            filename.unlink()
            logger.info("Uploaded and removed queued image: %s", filename)
        except Exception:
            logger.exception("Photo remains queued for retry: %s", filename)


def _upload_loop(stop_event):
    service = None
    credential = None
    try:
        while not stop_event.is_set():
            try:
                if service is None:
                    credential = ClientSecretCredential(
                        tenant_id=AZURE["tenant_id"],
                        client_id=AZURE["client_id"],
                        client_secret=AZURE["client_secret"],
                    )
                    service = BlobServiceClient(
                        account_url=f"https://{AZURE['storage_account']}.blob.core.windows.net",
                        credential=credential,
                        connection_timeout=10,
                        read_timeout=30,
                        retry_total=2,
                    )
                upload_pending_once(stop_event, service)
            except Exception:
                logger.exception("Upload worker failed; will retry")
            stop_event.wait(RETRY_SECONDS)
    finally:
        if service is not None:
            service.close()
        if credential is not None:
            credential.close()


def start_upload_worker(stop_event):
    if not AZURE_ENABLED:
        return None
    worker = threading.Thread(target=_upload_loop, args=(stop_event,), daemon=True)
    worker.start()
    return worker
