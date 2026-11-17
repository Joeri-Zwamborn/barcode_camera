"""Validate camera configuration without opening hardware."""
import re


def is_valid_camera_name(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", value) is not None


def parse_cameras(config):
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a mapping")
    if "cameras" in config:
        if "camera" in config:
            raise ValueError("Configure either camera or cameras, not both")
        entries = config["cameras"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("cameras must be a non-empty list")
    else:
        entries = [config["camera"]]
    result, names, sources = [], set(), set()
    for position, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError("Each camera must be a mapping")
        name = entry.get("name", f"camera{position}")
        if not is_valid_camera_name(name) or name.lower() in names:
            raise ValueError("Camera names must be unique, 1-32 ASCII letters/digits/hyphens/underscores, starting with a letter/digit")
        device = entry.get("device")
        if device is not None and device != "":
            source = device
            valid = isinstance(source, str) and bool(source.strip()) and source == source.strip()
        else:
            source = entry.get("index", 0)
            valid = type(source) is int and source >= 0
        if not valid:
            raise ValueError(f"Camera {name}: use a nonnegative index or a device path")
        # Treat /dev/video0 and index 0 as the same selection.
        node = re.fullmatch(r"/dev/video(\d+)", source) if isinstance(source, str) else None
        source_key = int(node.group(1)) if node else source
        if source_key in sources:
            raise ValueError(f"Camera {name}: the same device/index is configured twice")
        names.add(name.lower())
        sources.add(source_key)
        result.append({"name": name, "source": source})
    return result
