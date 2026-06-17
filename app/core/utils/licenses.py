"""
licenses.py — SPDX license list loader.

Reads from app/data/licenses.txt (one identifier per line).
If the file is missing or empty, fetches it from the SPDX GitHub repo once
in a background thread and writes it to disk for all future calls.

Public API:
    get_licenses()  -> list[str]   (returns [] if not yet ready)
    search_licenses(q, limit)  -> list[str]
    ensure_licenses_file(root)  — call at startup to trigger init if needed
"""
import os
import threading

_DATA_FILE = None          # set by ensure_licenses_file()
_cache: list[str] = []
_lock  = threading.Lock()
_ready = False


def _data_path(root: str) -> str:
    return os.path.join(root, 'app', 'data', 'licenses.txt')


def _load_from_disk(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [l.strip() for l in f if l.strip()]


def _fetch_and_write(path: str) -> None:
    """Download SPDX license identifiers from GitHub and save to path."""
    import urllib.request, json
    url = 'https://api.github.com/repos/spdx/license-list-XML/contents/src'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'rulezet/1.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        names = sorted(
            f['name'].replace('.xml', '')
            for f in data if f['name'].endswith('.xml')
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(names) + '\n')
        with _lock:
            global _cache, _ready
            _cache = names
            _ready = True
        print(f'[licenses] fetched {len(names)} SPDX identifiers')
    except Exception as e:
        print(f'[licenses] fetch failed: {e}')


def ensure_licenses_file(root: str) -> None:
    """
    Call once at app startup (outside request context).
    If the licenses file is missing or empty, starts a background fetch.
    Otherwise loads from disk into the in-memory cache.
    """
    global _DATA_FILE, _cache, _ready
    _DATA_FILE = _data_path(root)

    existing = _load_from_disk(_DATA_FILE)
    if existing:
        with _lock:
            _cache = existing
            _ready = True
        print(f'[licenses] loaded {len(_cache)} identifiers from disk')
    else:
        print('[licenses] file missing or empty — fetching from SPDX GitHub…')
        t = threading.Thread(target=_fetch_and_write, args=(_DATA_FILE,), daemon=True)
        t.start()


def get_licenses() -> list[str]:
    """Return all known SPDX license identifiers (empty list if not yet ready)."""
    with _lock:
        return list(_cache)


def search_licenses(q: str, limit: int = 30) -> list[str]:
    """Case-insensitive prefix + substring search over the license list."""
    with _lock:
        pool = _cache
    if not q:
        return pool[:limit]
    q_lower = q.lower()
    # Prefix matches first, then substring matches
    prefix = [s for s in pool if s.lower().startswith(q_lower)]
    rest   = [s for s in pool if not s.lower().startswith(q_lower) and q_lower in s.lower()]
    return (prefix + rest)[:limit]
