#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""funmap.py -- authoritative function boundaries for libil2cpp.so.

RVA assignment is ambiguous in this binary: the compiler packs small accessors
(`ldr x0,[x0,#off]; ret`) between real method bodies, and those accessors are
declared in dump.cs.  A naive "nearest declared RVA" therefore mis-attributes
addresses (e.g. 0x2006F18 lands inside get_ReloadStates, 0x200A470 inside
AddFireEffects).

funmap derives boundaries structurally instead: disassemble the main .text
image linearly and cut a new function whenever
  * the previous 4 bytes were `ret`, or
  * the previous 4 bytes were an unconditional `b <backward>` (tail call), or
  * the bytes were 0x00000000 padding.
Real function entries are then matched to declared methods by nearest RVA.

Output: funmap.json  ->  [{start, end, rva_declared|null, cls, decl}]
"""
import os, json, struct

ROOT = r'C:\Users\<USER>\Desktop\Android\SakuraUnpack'
SO = os.path.join(ROOT, r'_extract\lib\arm64-v8a\libil2cpp.so')
BUF = open(SO, 'rb').read()

# Section facts from the real ELF section table (verified via readelf/pyelf):
#   .text             0x1607D9C .. 0x1912E40   (shared-package / tooling C++)
#   il2cpp            0x1913E40 .. 0x39A9620   (the IL2CPP-generated method code)
#   .plt              0x39A9620 .. 0x39AB9D0
#   .data.rel.ro      0x39AC9D0 ..             (metadata; NOT code)
# Everything at or above 0x39AC9D0 is data.  CODE_HI must not exceed the end
# of .plt or the analyser will swallow metadata as one giant "function".
CODE_LO, CODE_HI = 0x1607D9C, 0x39AB9D0

M = json.load(open(os.path.join(ROOT, '_dump', 'methods2.json'), encoding='utf-8'))


def build():
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = True
    starts = {CODE_LO}
    base = CODE_LO - 0x1000
    data = BUF[base:CODE_HI - base]
    prev_end = None
    for i in md.disasm(data, CODE_LO):
        if prev_end is not None and prev_end != i.address:
            starts.add(i.address)          # skipped bytes -> new region
        if i.mnemonic == 'ret':
            starts.add(i.address + i.size)
        elif i.mnemonic == 'br':
            starts.add(i.address + i.size)     # indirect tail call / thunk end
        elif i.mnemonic == 'b':
            try:
                op = i.operands[0]
                if op.type == capstone.arm64.ARM64_OP_IMM and op.imm <= i.address:
                    starts.add(i.address + i.size)
            except Exception:
                pass
        prev_end = i.address + i.size
    starts = sorted(s for s in starts if CODE_LO <= s < CODE_HI)

    # map declared rva -> (cls, decl); only declared entries inside the code range
    regions = [(CODE_LO, CODE_HI)]
    decl = {}
    for e in M:
        r = e['rva']
        if any(lo <= r < hi for lo, hi in regions):
            decl.setdefault(r, (e['cls'], e['decl']))

    # walk function list; assign to the declared entry closest to the analysed
    # start (compilers place a 1-instruction `ret` stub before a real body, so
    # the true body start can be 4 bytes after the declared RVA).
    out = []
    sset = sorted(decl)
    import bisect
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else s
        if e - s < 4:
            continue
        j = bisect.bisect_left(sset, s)
        inner = []
        while j < len(sset) and sset[j] < e:
            inner.append(sset[j])
            j += 1
        if inner:
            r = min(inner, key=lambda x: abs(x - s))
            if abs(r - s) <= 0x14:
                cls, d = decl[r]
            else:
                r, cls, d = None, None, None
        else:
            r, cls, d = None, None, None
        out.append({'start': s, 'end': e, 'rva_declared': r,
                    'cls': cls, 'decl': d})
    return out


if __name__ == '__main__':
    fns = build()
    json.dump(fns, open(os.path.join(ROOT, '_dump', 'funmap.json'), 'w'), indent=0)
    named = [f for f in fns if f['rva_declared'] is not None]
    print('functions      :', len(fns))
    print('named          :', len(named))
    print('unnamed chunks :', len(fns) - len(named))
    print('bytes          : 0x%X' % sum(f['end'] - f['start'] for f in fns))
    for name, addr in [('ShootableWeapon.Awake', 0x2006F18),
                       ('DoFire', 0x2008A98),
                       ('Fire', 0x2009DF4),
                       ('Projectile.Initialize', 0x200A470),
                       ('Projectile.FixedUpdate', 0x2012560)]:
        for f in fns:
            if f['start'] <= addr < f['end']:
                print('  0x%X -> fn 0x%X..0x%X  %s::%s' % (
                    addr, f['start'], f['end'],
                    (f['cls'] or '?').split('.')[-1], (f['decl'] or '?').split('(')[0]))
                break
