"""rulecast.py — RuleCast submodule info cache.

Reads git metadata and parser list from modules/rulezet-cast/ at startup.
Call init_rulecast(root) once; then get_rulecast_info() everywhere.
"""
import os
import subprocess
import re

_info: dict = {}


def _run(cmd: list[str], cwd: str) -> str:
    try:
        return subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.DEVNULL,
                                       text=True, timeout=5).strip()
    except Exception:
        return ''


def _parse_version(describe: str) -> str:
    """Extract base semver from git describe output."""
    m = re.match(r'(v?\d+\.\d+[\.\d]*)', describe)
    return m.group(1).lstrip('v') if m else describe


KNOWN_FORMATS = [
    {'name': 'YARA',          'extension': '.yar .yara', 'file': 'yara_parser.py',     'status': 'stable'},
    {'name': 'Sigma',         'extension': '.yaml .yml', 'file': 'sigma_parser.py',    'status': 'stable'},
    {'name': 'Suricata',      'extension': '.rules',     'file': 'suricata_parser.py', 'status': 'stable'},
    {'name': 'CRS',           'extension': '.conf',      'file': 'crs_parser.py',      'status': 'stable'},
    {'name': 'NSE',           'extension': '.nse',       'file': 'nse_parser.py',      'status': 'stable'},
    {'name': 'Nova',          'extension': '.nov',       'file': 'nova_parser.py',     'status': 'stable'},
    {'name': 'Zeek',          'extension': '.zeek .bro', 'file': 'zeek_parser.py',     'status': 'stable'},
    {'name': 'Wazuh',         'extension': '.xml',       'file': 'wazuh_parser.py',    'status': 'stable'},
    {'name': 'Elastic',       'extension': '.toml',      'file': 'elastic_parser.py',  'status': 'stable'},
    {'name': 'ATR',           'extension': '.yaml .yml', 'file': 'atr_parser.py',      'status': 'stable'},
]


def init_rulecast(root: str) -> None:
    """Populate _info from the modules/rulezet-cast/ submodule."""
    global _info
    mod_path = os.path.join(root, 'modules', 'rulezet-cast')

    if not os.path.isdir(mod_path):
        _info = {'available': False, 'error': 'Submodule not found'}
        return

    parsers_dir = os.path.join(mod_path, 'parsers', 'formats')
    parser_files = []
    if os.path.isdir(parsers_dir):
        parser_files = [f for f in os.listdir(parsers_dir) if f.endswith('_parser.py')]

    # Mark which parsers are present on disk
    formats = []
    for fmt in KNOWN_FORMATS:
        present = fmt['file'] in parser_files
        formats.append({**fmt, 'present': present})

    # Git metadata
    describe   = _run(['git', 'describe', '--tags', '--always'], mod_path)
    version    = _parse_version(describe) if describe else '—'
    commit     = _run(['git', 'rev-parse', '--short', 'HEAD'], mod_path)
    commit_msg = _run(['git', 'log', '-1', '--format=%s'], mod_path)
    commit_date = _run(['git', 'log', '-1', '--format=%ci'], mod_path)
    branch     = _run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], mod_path)
    remote_url = _run(['git', 'remote', 'get-url', 'origin'], mod_path)

    # requirements.txt
    req_path = os.path.join(mod_path, 'requirements.txt')
    requirements = []
    if os.path.isfile(req_path):
        with open(req_path) as f:
            requirements = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    _info = {
        'available':    True,
        'path':         mod_path,
        'version':      version,
        'describe':     describe,
        'commit':       commit,
        'commit_msg':   commit_msg,
        'commit_date':  commit_date,
        'branch':       branch,
        'remote_url':   remote_url,
        'formats':      formats,
        'format_count': len([f for f in formats if f['present']]),
        'requirements': requirements,
    }


def get_rulecast_info() -> dict:
    return _info
