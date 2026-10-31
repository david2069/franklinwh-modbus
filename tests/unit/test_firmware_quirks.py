"""#91: firmware_quirks.json is well formed, public-only and loadable."""
import re
from pathlib import Path

from franklinwh_modbus.firmware_quirks import load_firmware_quirks, quirks_for

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'src' / 'franklinwh_modbus' / 'firmware_quirks.json'
VR = re.compile(r'^V\d+R\d+B\d+D\d+$')
REF = re.compile(r'^(david2069/[\w-]+#\d+|docs/[\w.-]+\.md)$')


def test_schema():
    q = load_firmware_quirks()
    vals = q['values']
    assert q['schema_version'] == 1
    for bid, b in q['behaviours'].items():
        assert re.fullmatch(r'[a-z0-9_]+', bid)
        assert b['point'] and b['description']
        assert b['our_assessment']['value'] in vals['our_assessment'] and b['our_assessment']['basis']
        vp = b['vendor_position']['value']
        assert vp in vals['vendor_position'] or re.fullmatch(r'fixed_in:V\d+R\d+B\d+D\d+', vp)
        assert isinstance(b['library_handling'], dict)
        assert b['observations'], bid
        for o in b['observations']:
            assert VR.match(o['firmware']), (bid, o)
            assert o['status'] in vals['status']
            assert o['site_count'] >= 1 and o['value']
            assert o['refs'] and all(REF.match(r) for r in o['refs']), (bid, o['refs'])
            if 'date' in o:
                assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', o['date'])


def test_doc_refs_exist():
    for b in load_firmware_quirks()['behaviours'].values():
        for o in b['observations']:
            for r in o['refs']:
                if r.startswith('docs/'):
                    assert (ROOT / r).exists(), r


def test_public_only():
    text = DATA.read_text()
    assert not re.search(r'\b(10|172|192)\.\d+\.\d+\.\d+\b', text)       # LAN IPs
    assert not re.search(r'\b[0-9A-F]{20}\b', text)                       # aGate serials
    assert not re.search(r'\b170\d\d\b', text)                            # private extension range
    assert not re.search(r'/Users/|/home/', text)
    assert 'writable' not in text.lower().replace('as writable', '')     # no writability claims


def test_quirks_for():
    v12 = quirks_for('V12R02B60D00')
    assert v12['m704_wset_sign'][0]['value'] == 'positive = discharge'
    # every observation for a firmware is kept, not just the last
    assert len(quirks_for('V10R01B04D00')['ext_15016_status']) == 3   # two reported + the #132 raw scan
    assert quirks_for(' V12R02B60D00 ') == v12
    assert quirks_for('V99R00B00D00') is None    # unknown is not "no quirks"
    assert quirks_for('') is None and quirks_for(None) is None
    v10 = quirks_for('V10R01B04D00', actionable_only=True)
    assert 'm715_controller_heartbeat' not in v10   # reported only


def test_packaged():
    # setuptools needs package-data for the JSON to ship in the wheel
    text = (ROOT / 'pyproject.toml').read_text()   # no tomllib on 3.10
    assert re.search(r'\[tool\.setuptools\.package-data\]\s*franklinwh_modbus = \[[^\]]*"firmware_quirks\.json"', text)


def test_extension_registers_each_have_an_entry():
    # #132: every public extension register 15000-15043 is recorded on its own
    b = load_firmware_quirks()['behaviours']
    own = {15013: 'ext_15013_battery_power', 15016: 'ext_15016_status', 15035: 'ext_15035_soc'}
    for a in range(15000, 15044):
        bid = own.get(a, f'ext_{a}')
        assert bid in b, a
        assert b[bid]['mapped'] is False
        fws = {o['firmware'] for o in b[bid]['observations']}
        assert {'V10R01B04D00', 'V12R02B60D00'} <= fws, a
    for bid, v in b.items():
        if bid.startswith('ext_'):
            assert isinstance(v['mapped'], bool), bid
