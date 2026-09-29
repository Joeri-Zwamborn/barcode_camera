import logging
import socket
import threading
from datetime import datetime, timezone

from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import ClientSecretCredential

from config import AZURE, HEARTBEAT, STATION_NAME


logger = logging.getLogger(__name__)


class HeartbeatReporter:
    def __init__(self):
        self.enabled = HEARTBEAT["enabled"]
        self.interval_seconds = HEARTBEAT["interval_seconds"]
        self.stop_event = threading.Event()
        self.thread = None
        self.table_client = None

    def start(self):
        if not self.enabled:
            return

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.enabled:
            return

        self.stop_event.set()
        self.thread.join()
        self._upload_status("offline")

    def _run(self):
        while not self.stop_event.is_set():
            self._upload_status("online")
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

    def _upload_status(self, status):
        try:
            self._get_table_client().upsert_entity(
                entity={
                    "PartitionKey": "barcode_camera",
                    "RowKey": STATION_NAME,
                    "status": status,
                    "last_seen_at": datetime.now(timezone.utc).isoformat(),
                    "hostname": socket.gethostname(),
                },
                mode=UpdateMode.REPLACE,
            )
            logger.info("Heartbeat uploaded: station=%s status=%s", STATION_NAME, status)
        except Exception:
            logger.exception("Failed to upload heartbeat")
