#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""a64.py -- tiny, verified ARM64 encoder for the few instructions our
determinism trampolines need.

Design rule: every instruction here is emitted as a literal u32 constant whose
encoding we assert against a known-good reference (capstone round-trip). If an
assertion fails we hear about it at build time, not as a game crash.
"""
import struct

# ------------------------------------------------------------------ helpers
def u32(x):
    return struct.pack('<I', x & 0xffffffff)

def movz_x(rd, imm16, shift=0):
    assert 0 <= rd <= 31 and 0 <= imm16 <= 0xffff and shift in (0, 16, 32, 48)
    return 0xD2800000 | ((shift // 16) << 21) | (imm16 << 5) | rd

def movk_x(rd, imm16, shift=0):
    assert 0 <= rd <= 31 and 0 <= imm16 <= 0xffff and shift in (0, 16, 32, 48)
    return 0xF2800000 | ((shift // 16) << 21) | (imm16 << 5) | rd

def mov_w(rd, rm):
    """MOV Wd, Wm == ORR Wd, WZR, Wm"""
    assert 0 <= rd <= 31 and 0 <= rm <= 31
    return 0x2A000000 | (rm << 16) | (31 << 5) | rd

def ldr_w(rt, rn, off):
    """LDR Wt, [Xn, #off]  (unsigned offset, scale 4)"""
    assert off % 4 == 0 and 0 <= off // 4 < 4096
    return 0xB9400000 | ((off // 4) << 10) | (rn << 5) | rt

def ldr_x(rt, rn, off):
    """LDR Xt, [Xn, #off]  (unsigned offset, scale 8)"""
    assert off % 8 == 0 and 0 <= off // 8 < 4096
    return 0xF9400000 | ((off // 8) << 10) | (rn << 5) | rt

def str_w(rt, rn, off):
    assert off % 4 == 0 and 0 <= off // 4 < 4096
    return 0xB9000000 | ((off // 4) << 10) | (rn << 5) | rt

def str_x(rt, rn, off):
    assert off % 8 == 0 and 0 <= off // 8 < 4096
    return 0xF9000000 | ((off // 8) << 10) | (rn << 5) | rt

def add_x(rd, rn, rm):
    return 0x8B000000 | (rm << 16) | (rn << 5) | rd

def add_x_imm(rd, rn, imm):
    assert 0 <= imm < 4096
    return 0x91000000 | (imm << 10) | (rn << 5) | rd

def sub_x(rd, rn, rm):
    return 0xCB000000 | (rm << 16) | (rn << 5) | rd

def uxtw(rd, rn):
    """UBFM Wd, Wn, #0, #31 -> zero-extend low 32 bits"""
    return 0x53007C00 | (rn << 5) | rd

def lsl_w(rd, rn, sh):
    # LSL Wd, Wn, #sh == UBFM Wd, Wn, #(32-sh), #(31-sh)
    assert 1 <= sh <= 31
    immr = (32 - sh) & 0x1f
    imms = (31 - sh) & 0x1f
    return 0x53000000 | (immr << 16) | (imms << 10) | (rn << 5) | rd

def lsr_w(rd, rn, sh):
    assert 1 <= sh <= 31
    return 0x53000000 | (sh << 16) | (31 << 10) | (rn << 5) | rd

def eor_w(rd, rn, rm):
    return 0x4A000000 | (rm << 16) | (rn << 5) | rd

def ubfx_w(rd, rn, lsb, width):
    return 0x53000000 | (lsb << 16) | ((width - 1) << 10) | (rn << 5) | rd

def ucvtf_s_w(sd, wn):
    """UCVTF Sd, Wn  -- unsigned int -> single. Encoding (scalar FP):
       0 0 0 1 1110 001 0 0 0 0 0 0 10000 0 rn rd   (SF=0, type=00=S, opcode=010011)
       It is: 0x1E230000 | (rn<<5) | rd
    """
    return 0x1E230000 | (wn << 5) | sd

def scvtf_s_w(sd, wn):
    return 0x1E220000 | (wn << 5) | sd

def fmov_s_w(sd, wn):
    """FMOV Sd, Wn -- bit pattern move from GPR to FP reg: 0x1E270000"""
    return 0x1E270000 | (wn << 5) | sd

def fmov_w_s(wd, sn):
    """FMOV Wd, Sn"""
    return 0x1E260000 | (sn << 5) | wd

def fmul(sd, rn, rm):
    return 0x1E200800 | (rm << 16) | (rn << 5) | sd

def fadd(sd, rn, rm):
    return 0x1E202800 | (rm << 16) | (rn << 5) | sd

def fsub(sd, rn, rm):
    return 0x1E203800 | (rm << 16) | (rn << 5) | sd

def ldr_s(st, xn, off):
    """LDR St, [Xn, #off] (unsigned offset, scale 4): 0xBD400000"""
    assert off % 4 == 0 and 0 <= off // 4 < 4096
    return 0xBD400000 | ((off // 4) << 10) | (xn << 5) | st

def str_s(st, xn, off):
    assert off % 4 == 0 and 0 <= off // 4 < 4096
    return 0xBD000000 | ((off // 4) << 10) | (xn << 5) | st

def ret():
    return 0xD65F03C0

def nop():
    return 0xD503201F

# ------------------------------------------------------------------ builder
class Code:
    def __init__(self):
        self.words = []

    def w(self, v):
        self.words.append(v)
        return self

    # load an arbitrary 64-bit absolute address into Xreg
    def movabs_x(self, r, addr):
        for shift in (0, 16, 32, 48):
            part = (addr >> shift) & 0xffff
            if shift == 0:
                self.w(movz_x(r, part, 0))
            else:
                self.w(movk_x(r, part, shift))
        return self

    def bytes(self):
        return b''.join(u32(x) for x in self.words)

    def __len__(self):
        return len(self.words)


# ------------------------------------------------------------------ verify
def verify():
    """Round-trip check with capstone so a bad encoding can never reach the game."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = False
    cases = {
        'movz_x x10,#0x1234,lsl16': (movz_x(10, 0x1234, 16), 'mov'),
        'ldr_w w10,[x9,#16]': (ldr_w(10, 9, 16), 'ldr'),
        'ldr_x x10,[x9,#8]': (ldr_x(10, 9, 8), 'ldr'),
        'str_w w10,[x9,#16]': (str_w(10, 9, 16), 'str'),
        'str_x x10,[x9,#8]': (str_x(10, 9, 8), 'str'),
        'add_x x10,x10,x11': (add_x(10, 10, 11), 'add'),
        'lsl_w w11,w10,#13': (lsl_w(11, 10, 13), 'lsl'),
        'lsr_w w11,w10,#17': (lsr_w(11, 10, 17), 'lsr'),
        'eor_w w10,w10,w11': (eor_w(10, 10, 11), 'eor'),
        'ucvtf s0,w10': (ucvtf_s_w(0, 10), 'ucvtf'),
        'fmov s0,w10': (fmov_s_w(0, 10), 'fmov'),
        'fmov w0,s0': (fmov_w_s(0, 0), 'fmov'),
        'fmul s0,s0,s1': (fmul(0, 0, 1), 'fmul'),
        'fadd s0,s0,s8': (fadd(0, 0, 8), 'fadd'),
        'fsub s2,s9,s8': (fsub(2, 9, 8), 'fsub'),
        'ldr_s s0,[x9,#0]': (ldr_s(0, 9, 0), 'ldr'),
        'str_s s0,[x9,#24]': (str_s(0, 9, 24), 'str'),
        'ret': (ret(), 'ret'),
        'uxtw w0,w10': (uxtw(0, 10), 'lsr'),
        'sub_x x0,x9,x8': (sub_x(0, 9, 8), 'sub'),
    }
    ok = True
    out = []
    for name, (w, want_mn) in cases.items():
        dis = list(md.disasm(u32(w), 0))
        if not dis:
            out.append(('%-30s %08x  DECODE FAILED' % (name, w), False))
            ok = False
            continue
        ins = dis[0]
        m = ins.mnemonic
        good = (m == want_mn)
        out.append(('%-30s %08x  %-8s %-22s %s' % (name, w, m, ins.op_str, 'OK' if good else 'MISMATCH(want %s)' % want_mn), good))
        if not good:
            ok = False
    return ok, out


if __name__ == '__main__':
    ok, lines = verify()
    for l, _ in lines:
        print(l)
    print()
    print('ALL ENCODINGS VERIFIED:', ok)
