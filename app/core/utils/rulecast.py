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
    {
        'name': 'YARA', 'extension': '.yar .yara', 'file': 'yara_parser.py', 'status': 'stable',
        'file_extension': 'yar',   'icon': 'fa-shield-halved', 'color': '#FF6B2B',
        'description': 'YARA malware detection rules — pattern matching for files and processes.',
        'can_be_executed': True,
    },
    {
        'name': 'Sigma', 'extension': '.yaml .yml', 'file': 'sigma_parser.py', 'status': 'stable',
        'file_extension': 'yml',   'icon': 'fa-chart-simple',  'color': '#0078D4',
        'description': 'Generic SIEM detection signatures — vendor-agnostic log search rules.',
        'can_be_executed': False,
    },
    {
        'name': 'Suricata', 'extension': '.rules', 'file': 'suricata_parser.py', 'status': 'stable',
        'file_extension': 'rules', 'icon': 'fa-fish',          'color': '#F4A300',
        'description': 'Suricata IDS/IPS network traffic detection rules.',
        'can_be_executed': True,
    },
    {
        'name': 'CRS', 'extension': '.conf', 'file': 'crs_parser.py', 'status': 'stable',
        'file_extension': 'conf',  'icon': 'fa-shield-cat',    'color': '#E53935',
        'description': 'OWASP Core Rule Set — ModSecurity WAF detection rules.',
        'can_be_executed': False,
    },
    {
        'name': 'NSE', 'extension': '.nse', 'file': 'nse_parser.py', 'status': 'stable',
        'file_extension': 'nse',   'icon': 'fa-network-wired', 'color': '#8BC34A',
        'description': 'Nmap Scripting Engine — Lua-based network service probes.',
        'can_be_executed': True,
    },
    {
        'name': 'Nova', 'extension': '.nov', 'file': 'nova_parser.py', 'status': 'stable',
        'file_extension': 'nov',   'icon': 'fa-robot',         'color': '#AB47BC',
        'description': 'Nova AI/LLM hunting rules for detecting adversarial AI behaviour.',
        'can_be_executed': False,
    },
    {
        'name': 'Zeek', 'extension': '.zeek .bro', 'file': 'zeek_parser.py', 'status': 'stable',
        'file_extension': 'zeek',  'icon': 'fa-magnifying-glass', 'color': '#00ACC1',
        'description': 'Zeek (formerly Bro) network analysis and detection scripts.',
        'can_be_executed': True,
    },
    {
        'name': 'Wazuh', 'extension': '.xml', 'file': 'wazuh_parser.py', 'status': 'stable',
        'file_extension': 'xml',   'icon': 'fa-server',        'color': '#00C853',
        'description': 'Wazuh SIEM/XDR detection rules in XML format.',
        'can_be_executed': False,
    },
    {
        'name': 'Elastic', 'extension': '.toml', 'file': 'elastic_parser.py', 'status': 'stable',
        'file_extension': 'toml',  'icon': 'fa-bolt',          'color': '#FDD835',
        'description': 'Elastic Security detection rules in TOML format.',
        'can_be_executed': False,
    },
    {
        'name': 'ATR', 'extension': '.yaml .yml', 'file': 'atr_parser.py', 'status': 'stable',
        'file_extension': 'yaml',  'icon': 'fa-brain',         'color': '#FF7043',
        'description': 'Agent Threat Rules — structured threat intelligence for AI agents.',
        'can_be_executed': False,
    },
]


def get_formats_for_db() -> list[dict]:
    """Return KNOWN_FORMATS shaped for FormatRule upsert."""
    return [
        {
            'name':            f['name'],
            'description':     f['description'],
            'file_extension':  f['file_extension'],
            'icon':            f['icon'],
            'color':           f['color'],
            'can_be_executed': f['can_be_executed'],
        }
        for f in KNOWN_FORMATS
    ]


def _find_cast_python(mod_path: str) -> tuple[str, str]:
    """
    Return (python_executable, cast_directory) — the python that can
    successfully run RuleCast and the directory it should run from.

    Tries the submodule venv first, then any sibling directory named
    rulezet-cast (local dev copy) walking up the tree.
    Falls back to ('python3', mod_path).
    """
    def _probe(py: str, directory: str) -> bool:
        try:
            r = subprocess.run(
                [py, '-c',
                 f'import sys; sys.path.insert(0,"{directory}"); '
                 'from parsers import ALL_PARSERS; print(len(ALL_PARSERS))'],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0 and r.stdout.strip().isdigit()
        except Exception:
            return False

    # 1. Submodule venv
    sub_py = os.path.join(mod_path, 'venv', 'bin', 'python')
    if os.path.isfile(sub_py) and _probe(sub_py, mod_path):
        return sub_py, mod_path

    # 2. Walk up from mod_path looking for a sibling named rulezet-cast
    search_root = mod_path
    for _ in range(5):
        search_root = os.path.dirname(search_root)
        if not search_root or search_root == '/':
            break
        for name in ('rulezet-cast', 'RuleCast', 'rulecast'):
            candidate_dir = os.path.join(search_root, name)
            if not os.path.isdir(candidate_dir):
                continue
            for py_name in ('venv/bin/python', 'venv/bin/python3'):
                py = os.path.join(candidate_dir, py_name)
                if os.path.isfile(py) and _probe(py, candidate_dir):
                    return py, candidate_dir

    return 'python3', mod_path


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

    python_path, cast_exec_dir = _find_cast_python(mod_path)

    _info = {
        'available':    True,
        'path':         mod_path,
        'python_path':  python_path,
        'cast_exec_dir': cast_exec_dir,
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
