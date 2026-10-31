"""Real pysunspec2 models built from raw register data (#130).

Tests that mock a model's structure can pass against code real pysunspec2
objects never take (the old ``m714.blocks``). Build the model from registers
instead, so attribute names and repeating groups are pysunspec2's own.
"""
import struct
from unittest.mock import MagicMock

import sunspec2.device as dev

NI16 = 0x8000     # SunSpec not-implemented values
NU16 = 0xFFFF


def u16(v):
    return v & 0xFFFF


def m714(dcw, dca=0, ports=(), dcwh_inj=0, dcwh_abs=0, sf=(0, 0, 0, 0, 0)):
    """Model 714 at PDU 1042. ``ports``: dicts with any of typ, dca, dcv, dcw,
    tmp, sta, idstr (raw register values; omitted ones are 0)."""
    regs = [0, 0, len(ports), u16(dca), u16(dcw)]
    regs += list(struct.unpack('>4H', struct.pack('>Q', dcwh_inj)))
    regs += list(struct.unpack('>4H', struct.pack('>Q', dcwh_abs)))
    regs += [u16(s) for s in sf]                       # DCA_SF DCV_SF DCW_SF DCWH_SF Tmp_SF
    for p in ports:
        idstr = p.get('idstr', '').encode().ljust(16, b'\0')
        regs += [p.get('typ', 1), 0] + list(struct.unpack('>8H', idstr))
        regs += [u16(p.get('dca', 0)), u16(p.get('dcv', 0)), u16(p.get('dcw', 0))]
        regs += [0] * 8                                # port DCWhInj, DCWhAbs
        regs += [u16(p.get('tmp', 0)), p.get('sta', 0), 0, 0]
    body = [714, len(regs)] + regs
    model = dev.Model(model_id=714, model_addr=1042, model_len=len(regs),
                      data=struct.pack(f'>{len(body)}H', *body))
    model.read = MagicMock(return_value=None)    # tests may set side_effect
    return model


def m714_v12(dcw=-600):
    """V12R02B60D00 as read on 2026-10-20 (#129): DCA 0, port block all 0."""
    return m714(dcw=dcw, dca=0, ports=[{'typ': 0, 'idstr': 'ID_String'}],
                dcwh_inj=7861360, dcwh_abs=8039960)
