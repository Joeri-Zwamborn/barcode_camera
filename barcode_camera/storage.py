import logging
import cv2
import os
import datetime
from config import SHAREPOINT_ENABLED

from config import LOCAL_SAVE_DIR

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
        if SHAREPOINT_ENABLED:
            try:
                upload_to_sharepoint(filename)
                logger.info("Uploaded image to Sharepoint: %s", filename)
            except Exception as e:
                logger.error("Failed to upload image to Sharepoint: %s", e)


    else:
        logger.error("Failed to save image: %s", filename)

def upload_to_sharepoint(filename):

    # TODO:
    # Upload using 
    # Office365-REST-Python-Client

    pass
