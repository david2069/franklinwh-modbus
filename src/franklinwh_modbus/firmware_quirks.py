"""Per-firmware aGate behaviour record (#91).

Reads the packaged ``firmware_quirks.json``. Read-only: nothing here changes
how the controller talks to the aGate.
"""
import json
from importlib import resources
from typing import Any, Dict, List, Optional

ACTIONABLE = ('documented', 'measured')

_cache: Optional[Dict[str, Any]] = None


def load_firmware_quirks() -> Dict[str, Any]:
    """Return the whole record (schema, values, behaviours)."""
    global _cache
    if _cache is None:
        text = resources.files(__package__).joinpath('firmware_quirks.json').read_text(encoding='utf-8')
        _cache = json.loads(text)
    return _cache


def quirks_for(firmware: Optional[str], actionable_only: bool = False) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """Observations for one firmware (M1 ``Vr``), keyed by behaviour id.

    Each value is a list of every observation for that firmware, in file order;
    a behaviour can have more than one (e.g. different dates or conditions).

    Returns None for an unknown or empty firmware: unknown is not "no quirks".
    With ``actionable_only``, only 'documented' and 'measured' observations.
    """
    vr = (firmware or '').strip()
    if not vr:
        return None
    out = {}
    for bid, b in load_firmware_quirks()['behaviours'].items():
        for obs in b['observations']:
            if obs['firmware'] == vr and (not actionable_only or obs['status'] in ACTIONABLE):
                out.setdefault(bid, []).append(obs)
    known = {o['firmware'] for b in load_firmware_quirks()['behaviours'].values() for o in b['observations']}
    return out if vr in known else None
