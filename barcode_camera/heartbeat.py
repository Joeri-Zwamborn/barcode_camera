import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import ClientSecretCredential

from config import AZURE, HEARTBEAT, STATION_NAME


logger = logging.getLogger(__name__)
SOFTWARE_VERSION = (Path(__file__).resolve().parent.parent / "VERSION").read_text(
    encoding="utf-8"
).strip()


class HeartbeatReporter:
    def __init__(self):
        self.enabled = HEARTBEAT["enabled"]
        self.interval_seconds = HEARTBEAT["interval_seconds"]
        self.stop_event = threading.Event()
        self.thread = None
        self.table_client = None
        self.lock = threading.Lock()
        self.camera_status = "offline"
        self.scanner_status = "offline"
        self.last_barcode = ""
        self.last_upload = ""

    def start(self):
        if not self.enabled:
            return

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.enabled:
            return

        self.stop_event.set()
        if self.thread is not None:
            self.thread.join()
        self.set_camera_status("offline")
        self.set_scanner_status("offline")
        self._upload_heartbeat()

    def set_camera_status(self, status):
        with self.lock:
            self.camera_status = status

    def set_scanner_status(self, status):
        with self.lock:
            self.scanner_status = status

    def record_barcode(self, barcode):
        with self.lock:
            self.last_barcode = barcode

    def record_upload(self):
        with self.lock:
            self.last_upload = datetime.now(timezone.utc).isoformat()

    def _run(self):
        while not self.stop_event.is_set():
            self._upload_heartbeat()
            self.stop_event.wait(self.interval_seconds)

    def _get_table_client(self):
        if self.table_client is not None:
            return self.table_client

        credential = ClientSecretCredential(
            tenant_id=AZURE["tenant_id"],
            client_id=AZURE["client_id"],
            client_secret=AZURE["client_secret"],
        )
        service = TableServiceClient(
            endpoint=f"https://{AZURE['storage_account']}.table.core.windows.net",
            credential=credential,
        )
        service.create_table_if_not_exists(HEARTBEAT["table"])
        self.table_client = service.get_table_client(HEARTBEAT["table"])
        return self.table_client

    def _upload_heartbeat(self):
        try:
            with self.lock:
                entity = {
                    "PartitionKey": STATION_NAME,
                    "RowKey": "current",
                    "LastSeen": datetime.now(timezone.utc).isoformat(),
                    "CameraStatus": self.camera_status,
                    "ScannerStatus": self.scanner_status,
                    "LastBarcode": self.last_barcode,
                    "LastUpload": self.last_upload,
                    "SoftwareVersion": SOFTWARE_VERSION,
                }
            self._get_table_client().upsert_entity(
                entity=entity,
                mode=UpdateMode.REPLACE,
            )
            logger.info("Heartbeat uploaded: station=%s", STATION_NAME)
        except Exception:
            logger.exception("Failed to upload heartbeat")
