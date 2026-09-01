import logging
import cv2
import os
import datetime
from config import AZURE_ENABLED, LOCAL_SAVE_DIR, AZURE
from pathlib import Path
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient


logger = logging.getLogger(__name__)

os.makedirs(LOCAL_SAVE_DIR, exist_ok=True)

def save_image(barcode, frame):
    now = datetime.datetime.now()
    filename = os.path.join(
        LOCAL_SAVE_DIR,
        f"{barcode}_{now}.png"
    )

    if cv2.imwrite(filename, frame):
        logger.info("Saved image: %s", filename)
        # Placeholder
        if AZURE_ENABLED:
            try:
                upload_to_azure(filename)
                logger.info("Uploaded image to Azure: %s", filename)
            except Exception as e:
                logger.error("Failed to upload image to Azure: %s", e)


    else:
        logger.error("Failed to save image: %s", filename)

def upload_to_azure(filename):
    credential = ClientSecretCredential(
        tenant_id=AZURE["tenant_id"],
        client_id=AZURE["client_id"],
        client_secret=AZURE["client_secret"],
    )

    service = BlobServiceClient(
        account_url=(
            f"https://{AZURE['storage_account']}.blob.core.windows.net"
        ),
        credential=credential,
    )

    local_file = Path(filename)
    blob = service.get_blob_client(
        container=AZURE["container"],
        blob=local_file.name,
    )

    with local_file.open("rb") as image_file:
        blob.upload_blob(image_file, overwrite=False)