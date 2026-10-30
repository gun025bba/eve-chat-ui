"""Resolve historical source paths after content-identical legacy moves."""
from pathlib import Path

SOURCES = {'memory-api.js': 'src/api/memory.js', 'proactive-api.js': 'src/api/proactive.js', 'shell.js': 'src/app/shell.js', 'pim.js': 'src/features/pim/index.js', 'briefing.js': 'src/features/briefing/index.js', 'proactive.js': 'src/features/proactive/index.js', 'memory.js': 'src/features/memory/index.js', 'today.js': 'src/features/today/index.js'}
ROOT = Path(__file__).resolve().parent.parent
def source_path(path):
    candidate = Path(path).resolve()
    legacy = ROOT / SOURCES.get(candidate.name, 'src/legacy/' + candidate.name)
    return legacy if candidate.parent == ROOT and not candidate.exists() and legacy.is_file() else candidate

def source_text(path):
    candidate = source_path(path)
    if candidate == ROOT / 'src/features/proactive/index.js':
        parts = [candidate.parent / 'model.js', candidate.parent / 'confirm-card.js', candidate]
        return '\n'.join(part.read_text() for part in parts if part.exists())
    return candidate.read_text()
