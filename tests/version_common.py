"""The reviewed package version is the single release-version source."""
import json
from pathlib import Path

VERSION = json.loads((Path(__file__).resolve().parent.parent / 'package.json').read_text())['version']

def versioned(text):
    return text.replace('__EVE_VERSION__', VERSION)
