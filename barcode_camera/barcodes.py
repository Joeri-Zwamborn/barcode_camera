"""Barcode rules shared by scanner input and image storage."""
import re

MAX_BARCODE_LENGTH = 128
_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', re.ASCII)


def is_valid_barcode(value):
    return isinstance(value, str) and _PATTERN.fullmatch(value) is not None
