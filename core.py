"""Pure, testable text preparation and scheduling helpers for TypeForge Studio."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import random
import re

PLACEHOLDER = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")

@dataclass
class Profile:
    name: str = 'Balanced'
    wpm: int = 65
    jitter: int = 22  # percent
    typo_percent: float = 0.0
    punctuation_pause_ms: int = 240
    paragraph_pause_ms: int = 420
    countdown: int = 5
    shift_enter: bool = True
    tabs_as_spaces: bool = True
    stop_on_focus_loss: bool = True

    def clean(self) -> 'Profile':
        return Profile(
            name=str(self.name)[:80], wpm=max(10, min(220, int(self.wpm))),
            jitter=max(0, min(65, int(self.jitter))),
            typo_percent=max(0.0, min(6.0, float(self.typo_percent))),
            punctuation_pause_ms=max(0, min(3000, int(self.punctuation_pause_ms))),
            paragraph_pause_ms=max(0, min(5000, int(self.paragraph_pause_ms))),
            countdown=max(2, min(15, int(self.countdown))),
            shift_enter=bool(self.shift_enter), tabs_as_spaces=bool(self.tabs_as_spaces),
            stop_on_focus_loss=bool(self.stop_on_focus_loss),
        )

PRESETS = {
    'Balanced': Profile(),
    'Precision': Profile('Precision', 55, 10, 0, 180, 300),
    'Natural': Profile('Natural', 70, 32, 1.3, 320, 620),
    'Fast': Profile('Fast', 140, 8, 0, 90, 150),
    'Presentation': Profile('Presentation', 40, 28, 0, 450, 800),
}

NEIGHBORS = {
    'q':'wa','w':'qeas','e':'wrsd','r':'etdf','t':'ryfg','y':'tugh',
    'u':'yihj','i':'uojk','o':'ipkl','p':'ol','a':'qwsz','s':'awedxz',
    'd':'serfcx','f':'drtgvc','g':'ftyhbv','h':'gyujnb','j':'huikmn',
    'k':'jiolm','l':'kop','z':'asx','x':'zsdc','c':'xdfv','v':'cfgb',
    'b':'vghn','n':'bhjm','m':'njk',
}


def parse_variables(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for no, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'Variable line {no} needs a name=value pair.')
        key, value = line.split('=', 1)
        key = key.strip()
        if not re.fullmatch(r'[\w.-]+', key):
            raise ValueError(f'Invalid variable name on line {no}.')
        result[key] = value.strip()
    return result


def expand_template(text: str, variables: dict[str, str] | None = None, *,
                    now: datetime | None = None, clipboard: str | None = None) -> str:
    now = now or datetime.now()
    values = {'date': now.strftime('%Y-%m-%d'), 'time': now.strftime('%H:%M'),
              'datetime': now.strftime('%Y-%m-%d %H:%M')}
    if clipboard is not None:
        values['clipboard'] = clipboard
    # User-defined keys can intentionally override built-ins.
    values.update(variables or {})
    missing = set()

    def replacement(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            missing.add(key)
            return m.group(0)
        return values[key]

    out = PLACEHOLDER.sub(replacement, text)
    if missing:
        raise ValueError('Missing variables: ' + ', '.join(sorted(missing)))
    return out


def prepare_text(text: str, *, tabs_as_spaces: bool = True) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if tabs_as_spaces:
        text = text.replace('\t', '    ')
    invalid = [ch for ch in text if ord(ch) < 32 and ch not in '\t\n']
    if invalid:
        raise ValueError('Input contains unsupported control characters.')
    return text


def keystroke_delay(ch: str, prev: str, profile: Profile, rng: random.Random) -> float:
    """Delay in seconds, inclusive of optional punctuation/paragraph pauses."""
    p = profile.clean()
    base = 12.0 / p.wpm  # 5 characters per word
    variance = rng.uniform(-p.jitter / 100.0, p.jitter / 100.0)
    delay = base * (1 + variance)
    if ch == ' ':
        delay *= 1.08
    if ch in ',;:،؛':
        delay += p.punctuation_pause_ms / 1000 * .6
    if ch in '.!?؟':
        delay += p.punctuation_pause_ms / 1000
    if ch == '\n':
        delay += p.paragraph_pause_ms / 1000 * (1.3 if prev == '\n' else .55)
    return max(.012, delay)


def choose_typo(ch: str, profile: Profile, rng: random.Random) -> str | None:
    low = ch.lower()
    if low not in NEIGHBORS or rng.random() >= profile.clean().typo_percent / 100:
        return None
    wrong = rng.choice(NEIGHBORS[low])
    return wrong.upper() if ch.isupper() else wrong


def estimate_seconds(text: str, profile: Profile) -> float:
    rng = random.Random(0)
    total = 0.0
    prev = ''
    for ch in text:
        total += keystroke_delay(ch, prev, profile, rng)
        prev = ch
    total += len(text) * (profile.clean().typo_percent / 100) * .24
    return total


def format_duration(value: float) -> str:
    sec = max(0, round(value))
    if sec >= 3600:
        return f'{sec//3600}h {(sec%3600)//60}m'
    if sec >= 60:
        return f'{sec//60}m {sec%60}s'
    return f'{sec}s'