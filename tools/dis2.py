#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ARM64 mini-disassembler for the subset of instructions used by IL2CPP output."""
import struct, sys, os

ROOT = r'C:\Users\<USER>\Desktop\Android\SakuraUnpack'
ORIG = open(os.path.join(ROOT, r'_extract\lib\arm64-v8a\libil2cpp.so'), 'rb').read()

CONDS = ['eq', 'ne', 'hs', 'lo', 'mi', 'pl', 'vs', 'vc', 'hi', 'ls', 'ge', 'lt', 'gt', 'le', 'al', 'nv']
R32 = ['w%d' % i for i in range(31)] + ['wzr']
R64 = ['x%d' % i for i in range(31)] + ['xzr']


def word(buf, rva):
    off = rva - 0x1000
    if off < 0 or off + 4 > len(buf):
        return None
    return struct.unpack_from('<I', buf, off)[0]


def sext(v, bits):
    if v & (1 << (bits - 1)):
        v -= (1 << bits)
    return v


def decode(w, addr):
    if w is None:
        return '???'
    # branch reg / ret
    if w == 0xD65F03C0:
        return 'ret'
    if w == 0xD503201F:
        return 'nop'
    if w == 0xD503207F:
        return 'nop2'
    if (w & 0xFFFFFC1F) == 0xD61F0000:
        return 'br x%d' % ((w >> 5) & 0x1F)
    if (w & 0xFFFFFC1F) == 0xD63F0000:
        return 'blr x%d' % ((w >> 5) & 0x1F)
    if w == 0xD65F0BFF:
        return 'ret'
    # B
    if (w & 0xFC000000) == 0x14000000:
        imm = sext(w & 0x3FFFFFF, 26)
        return 'b 0x%X' % (addr + imm * 4)
    if (w & 0xFC000000) == 0x94000000:
        imm = sext(w & 0x3FFFFFF, 26)
        return 'bl 0x%X' % (addr + imm * 4)
    # B.cond
    if (w & 0xFF000010) == 0x54000000:
        imm = sext((w >> 5) & 0x7FFFF, 19)
        return 'b.%s 0x%X' % (CONDS[w & 0xF], addr + imm * 4)
    # CBZ / CBNZ
    if (w & 0x7E000000) == 0x34000000:
        sf = (w >> 31) & 1
        op = (w >> 24) & 1
        rt = w & 0x1F
        imm = sext((w >> 5) & 0x7FFFF, 19)
        return '%s %s, 0x%X' % ('cbnz' if op else 'cbz', (R64 if sf else R32)[rt], addr + imm * 4)
    # TBZ / TBNZ
    if (w & 0x7E000000) == 0x36000000:
        op = (w >> 24) & 1
        b = ((w >> 31) << 5) | ((w >> 19) & 0x1F)
        rt = w & 0x1F
        imm = sext((w >> 5) & 0x3FFF, 14)
        return '%s w%d, #%d, 0x%X' % ('tbnz' if op else 'tbz', rt, b, addr + imm * 4)
    # ADRP
    if (w & 0x9F000000) == 0x90000000:
        rd = w & 0x1F
        immhi = (w >> 5) & 0x7FFFF
        immlo = (w >> 29) & 3
        imm = sext((immhi << 2) | immlo, 21) << 12
        return 'adrp x%d, 0x%X' % (rd, (addr & ~0xFFF) + imm)
    # ADD/SUB immediate
    if (w & 0x1F000000) == 0x11000000:
        sf = (w >> 31) & 1
        op = (w >> 30) & 1
        s = (w >> 29) & 1
        sh = (w >> 22) & 1
        imm12 = (w >> 10) & 0xFFF
        rn = (w >> 5) & 0x1F
        rd = w & 0x1F
        if sh:
            imm12 <<= 12
        nm = ('sub' if op else 'add') + ('s' if s else '')
        return '%s %s, %s, #0x%X' % (nm, (R64 if sf else R32)[rd], (R64 if sf else R32)[rn], imm12)
    # ORR / AND / EOR / MOV (register) — mask out bit21 and bit15-10 shift field
    if (w & 0x1F200000) == 0x0A000000:
        sf = (w >> 31) & 1
        opc = (w >> 29) & 3
        rm = (w >> 16) & 0x1F
        rn = (w >> 5) & 0x1F
        rd = w & 0x1F
        shift = (w >> 22) & 3
        imm6 = (w >> 10) & 0x3F
        nm = ['and', 'orr', 'eor', 'ands'][opc]
        if nm == 'orr' and rn == 31 and shift == 0 and imm6 == 0:
            return 'mov %s, %s' % ((R64 if sf else R32)[rd], (R64 if sf else R32)[rm])
        return '%s %s, %s, %s' % (nm, (R64 if sf else R32)[rd], (R64 if sf else R32)[rn], (R64 if sf else R32)[rm])
    # MOV (immediate)  / MOVZ / MOVN
    if (w & 0x1F800000) == 0x12800000:
        sf = (w >> 31) & 1
        op = (w >> 30) & 1
        hw = (w >> 21) & 3
        imm16 = (w >> 5) & 0xFFFF
        rd = w & 0x1F
        v = imm16 << (hw * 16)
        if sf == 0:
            v &= 0xFFFFFFFF
        if op:
            v = (~v) & (0xFFFFFFFFFFFFFFFF if sf else 0xFFFFFFFF)
        return 'mov %s, #0x%X' % ((R64 if sf else R32)[rd], v)
    # LDR/STR unsigned immediate (imm12 scaled)  -- rt is the LOW 5 bits for LDR/STR
    if (w & 0x3B000000) == 0x39000000:
        size = (w >> 30) & 3
        opc = (w >> 22) & 3
        rn = (w >> 5) & 0x1F
        rt = w & 0x1F
        off = ((w >> 10) & 0xFFF) << size
        load = (opc & 1) == 1
        if not load:
            nm = ['strb', 'strh', 'str', 'str'][opc]
            sz = size
        else:
            nm = ['ldrb', 'ldrh', 'ldr', 'ldrsw'][opc]
            sz = 3 if opc == 3 else size
        reg = (R64 if sz == 3 else R32)[rt]
        rnb = 'sp' if rn == 31 else 'x%d' % rn
        return '%s %s, [%s, #0x%X]' % (nm, reg, rnb, off)
    # LDP/STP all addressing forms (opc: 0=S32,1=D64,2=Q128)
    if (w & 0x3A000000) == 0x28000000 and ((w >> 26) & 1) == 0:
        opc = (w >> 30) & 3
        idx = (w >> 23) & 3
        load = (w >> 22) & 1
        rn = (w >> 5) & 0x1F
        rt = w & 0x1F
        rt2 = (w >> 10) & 0x1F
        imm = sext((w >> 15) & 0x7F, 7)
        scale = [3, 3, 2, 2][opc]
        off = imm << scale
        nm = 'ldp' if load else 'stp'
        regs = (R64, R64, R32, R32)[opc]
        a = regs[rt]
        b = regs[rt2]
        rnb = 'sp' if rn == 31 else 'x%d' % rn
        if idx == 1:
            return '%s %s, %s, [%s], #%d' % (nm, a, b, rnb, off)
        if idx == 3:
            return '%s %s, %s, [%s, #%d]!' % (nm, a, b, rnb, off)
        return '%s %s, %s, [%s, #%d]' % (nm, a, b, rnb, off)
    # LDR literal
    if (w & 0x3B000000) == 0x18000000:
        opc = (w >> 30) & 3
        rt = w & 0x1F
        imm = sext((w >> 5) & 0x7FFFF, 19)
        return 'ldr %s, 0x%X' % ((['w', 'x', 's', 'd'][opc] + str(rt)), addr + imm * 4)
    # CMP (SUBS imm / reg)
    if (w & 0x7F800000) == 0x71000000:
        sf = (w >> 31) & 1
        rn = (w >> 5) & 0x1F
        imm = (w >> 10) & 0xFFF
        return 'cmp %s, #0x%X' % ((R64 if sf else R32)[rn], imm)
    if (w & 0x7F200000) == 0x6B000000:
        sf = (w >> 31) & 1
        rn = (w >> 5) & 0x1F
        rm = (w >> 16) & 0x1F
        return 'cmp %s, %s' % ((R64 if sf else R32)[rn], (R64 if sf else R32)[rm])
    return '?'


def dis(rva, n, buf=None):
    buf = buf if buf is not None else ORIG
    for k in range(n):
        a = rva + 4 * k
        w = word(buf, a)
        if w is None:
            print('  0x%08X  <EOF>' % a)
            return
        print('  0x%08X  %08X  %s' % (a, w, decode(w, a)))


if __name__ == '__main__':
    rva = int(sys.argv[1], 16)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    dis(rva, n)
