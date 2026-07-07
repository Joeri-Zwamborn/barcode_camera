import cv2
import os
import datetime

from config import LOCAL_SAVE_DIR

os.makedirs(LOCAL_SAVE_DIR, exist_ok=True)
now = datetime.datetime.now()

def save_image(barcode, frame):

    filename = os.path.join(
        LOCAL_SAVE_DIR,
        f"{barcode + now}.png"
    )

    if cv2.imwrite(filename, frame):
        print("Saved:", filename)

        # Placeholder
        upload_to_sharepoint(filename)

    else:
        print("Save failed")


def upload_to_sharepoint(filename):

    # TODO:
    # Upload using Microsoft Graph
    # or Office365-REST-Python-Client

    pass
