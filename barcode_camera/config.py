from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

with CONFIG_PATH.open(encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

# OpenCV accepts either a numeric index or a stable video-device path.
CAMERA_INDEX = config["camera"].get("device") or config["camera"].get("index", 0)
SCANNER_DEVICE = config["scanner"]["device"]
LOCAL_SAVE_DIR = config["storage"]["local_directory"]

AZURE_ENABLED = config["azure"]["enabled"]
AZURE = config["azure"]

STATION_NAME = config["station"]["name"]
HEARTBEAT = {
    "enabled": False,
    "table": "deviceheartbeats",
    "interval_seconds": 60,
} | config.get("heartbeat", {})
