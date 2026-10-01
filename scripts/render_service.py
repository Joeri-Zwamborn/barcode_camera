"""Render the service unit for this checkout and its non-root owner."""
from pathlib import Path
import re
import sys


def quote_path(path):
    value = str(path)
    if '\n' in value or '\r' in value:
        raise ValueError('Service paths cannot contain newlines')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def render_service(directory, user):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*[$]?', user) or user == 'root':
        raise ValueError('Use a valid non-root service account')
    directory = Path(directory).resolve()
    template = (directory / 'barcode_camera.service.in').read_text()
    substitutions = {
        '@SERVICE_USER@': user,
        '@APP_DIRECTORY@': quote_path(directory),
        '@PYTHON_EXECUTABLE@': quote_path(directory / 'venv' / 'bin' / 'python'),
        '@MAIN_SCRIPT@': quote_path(directory / 'barcode_camera' / 'main.py'),
    }
    for token, value in substitutions.items():
        template = template.replace(token, value)
    return template


if __name__ == '__main__':
    sys.stdout.write(render_service(sys.argv[1], sys.argv[2]))
