"""Local-only preference and explicitly saved snippet persistence."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import json
import os
import tempfile
from core import Profile

ROOT = Path(os.environ.get('APPDATA', str(Path.home()))) / 'TypeForgeStudio'

def _read(name, default):
    try:
        data = json.loads((ROOT / name).read_text(encoding='utf-8'))
        return data if isinstance(data, type(default)) else default
    except (ValueError, OSError, TypeError):
        return default

def _write(name, data):
    ROOT.mkdir(parents=True, exist_ok=True)
    # atomic replace to avoid half-written settings on sudden shutdown
    fd, temp = tempfile.mkstemp(prefix='tf-', suffix='.json', dir=str(ROOT))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        os.replace(temp, ROOT / name)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def load_profile():
    data = _read('preferences.json', {})
    known = Profile.__dataclass_fields__
    try:
        return Profile(**{k: v for k, v in data.items() if k in known}).clean()
    except (ValueError, TypeError):
        return Profile()

def save_profile(profile):
    _write('preferences.json', asdict(profile.clean()))

def load_snippets():
    data = _read('snippets.json', [])
    return [{'name': str(x.get('name', 'Untitled'))[:120],
             'text': str(x.get('text',''))} for x in data if isinstance(x, dict)]

def save_snippets(items):
    _write('snippets.json', items)

def load_history():
    return _read('history.json', [])[-40:]

def append_history(entry):
    hist = load_history()
    hist.append(entry)
    _write('history.json', hist[-40:])