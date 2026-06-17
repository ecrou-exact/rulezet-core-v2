"""rulecast_core.py — Business logic for the RuleCast admin section."""
from ...core.utils.rulecast import get_rulecast_info


def get_cast_info() -> dict:
    """Return cached RuleCast submodule metadata."""
    return get_rulecast_info()
