"""Resolve historical source paths after content-identical legacy moves."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def source_path(path):
    candidate = Path(path).resolve()
    legacy = ROOT / 'src' / 'legacy' / candidate.name
    return legacy if candidate.parent == ROOT and not candidate.exists() and legacy.is_file() else candidate
