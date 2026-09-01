from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

with CONFIG_PATH.open(encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

CAMERA_INDEX = config["camera"]["index"]
SCANNER_DEVICE = config["scanner"]["device"]
LOCAL_SAVE_DIR = config["storage"]["local_directory"]

AZURE_ENABLED = config["azure"]["enabled"]
AZURE = config["azure"]