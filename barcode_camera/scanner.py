from evdev import InputDevice, categorize, ecodes
from config import SCANNER_DEVICE
import logging  

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BarcodeScanner:
    """
    Reads a USB HID barcode scanner.

    Yields one complete barcode every time the scanner sends ENTER.
    """

    SHIFT_KEYS = {
        "KEY_LEFTSHIFT",
        "KEY_RIGHTSHIFT"
    }

    KEYMAP = {
        # Numbers
        "KEY_1": ("1", "!"),
        "KEY_2": ("2", "@"),
        "KEY_3": ("3", "#"),
        "KEY_4": ("4", "$"),
        "KEY_5": ("5", "%"),
        "KEY_6": ("6", "^"),
        "KEY_7": ("7", "&"),
        "KEY_8": ("8", "*"),
        "KEY_9": ("9", "("),
        "KEY_0": ("0", ")"),

        # Symbols
        "KEY_MINUS": ("-", "_"),
        "KEY_EQUAL": ("=", "+"),
        "KEY_LEFTBRACE": ("[", "{"),
        "KEY_RIGHTBRACE": ("]", "}"),
        "KEY_BACKSLASH": ("\\", "|"),
        "KEY_SEMICOLON": (";", ":"),
        "KEY_APOSTROPHE": ("'", "\""),
        "KEY_GRAVE": ("`", "~"),
        "KEY_COMMA": (",", "<"),
        "KEY_DOT": (".", ">"),
        "KEY_SLASH": ("/", "?"),
        "KEY_SPACE": (" ", " "),
    }

    def __init__(self):
        try:
            self.device = InputDevice(SCANNER_DEVICE)
            logger.info(f"Scanner device initialized: {SCANNER_DEVICE}")
        except Exception:
            logger.exception("Failed to initialize scanner device.")
            raise
        self.shift = False

    def __iter__(self):

        barcode = ""
        try:
            for event in self.device.read_loop():

                if event.type != ecodes.EV_KEY:
                    continue

                key = categorize(event)

                code = key.keycode

                if isinstance(code, list):
                    code = code[0]

                # Key pressed
                if key.keystate == key.key_down:

                    if code in self.SHIFT_KEYS:
                        self.shift = True
                        continue

                    if code == "KEY_ENTER":

                        if barcode:
                            logger.info(f"Barcode scanned: {barcode}")
                            yield barcode
                            barcode = ""

                        continue

                    # Letters
                    if code.startswith("KEY_"):

                        value = code[4:]

                        if len(value) == 1 and value.isalpha():

                            barcode += (
                                value.upper()
                                if self.shift
                                else value.lower()
                            )

                            continue

                    # Symbols
                    if code in self.KEYMAP:

                        normal, shifted = self.KEYMAP[code]

                        barcode += shifted if self.shift else normal

                elif key.keystate == key.key_up:

                    if code in self.SHIFT_KEYS:
                        self.shift = False
        except Exception:
            logger.exception("An error occurred while reading from the scanner.")
            raise
