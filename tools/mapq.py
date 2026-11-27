#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mapq.py -- query funmap.json + disassemble, with correct attribution."""
import os, sys, json, bisect
import capstone

ROOT = r'C:\Users\<USER>\Desktop\Android\SakuraUnpack'
SO = os.path.join(ROOT, r'_extract\lib\arm64-v8a\libil2cpp.so')
BUF = open(SO, 'rb').read()
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
FN = json.load(open(os.path.join(ROOT, '_dump', 'funmap.json'), encoding='utf-8'))
S = [f['start'] for f in FN]


def fn_of(addr):
    k = bisect.bisect_right(S, addr) - 1
    if k < 0:
        return None
    f = FN[k]
    if addr >= f['end']:
        return None
    return f


def nm(f):
    if not f:
        return '?'
    if f['cls']:
        return '%s::%s' % (f['cls'].split('.')[-1], f['decl'].split('(')[0])
    return 'chunk@0x%X' % f['start']


def dis(a, n=40):
    off = a - 0x1000
    for i in md.disasm(BUF[off:off + n * 4], a):
        f = fn_of(i.address)
        print('  0x%08X  %-10s %-40s | %s+0x%X' % (
            i.address, i.mnemonic, i.op_str, nm(f),
            i.address - f['start'] if f else 0))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'at':
        for a in sys.argv[2:]:
            a = int(a, 16)
            f = fn_of(a)
            print('0x%X -> %s +0x%X   (fn 0x%X..0x%X, decl=%s)' % (
                a, nm(f), a - f['start'] if f else -1,
                f['start'] if f else 0, f['end'] if f else 0,
                hex(f['rva_declared']) if f and f['rva_declared'] else None))
    elif cmd == 'dis':
        dis(int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 40)
    elif cmd == 'named':
        lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0
        for f in FN:
            if f['cls'] and lo <= f['start'] < lo + 0x100000:
                print('0x%X..0x%X  %s' % (f['start'], f['end'], nm(f)))
