#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_v100.py -- v100: player 8x, AI back to stock.

Two actions on the SAME hook (ShootableWeapon.TryUse 0x200891C):

  player  (this.m_Character == SystemManager.m_Character):
        s9 = m_ShootDelay * 0.5        (v85 gave 0.25/FireRate -> 0.125/FireRate = 8x stock)

  AI      (anything else):
        s9 = m_ShootDelay * 4.0, and ALSO write it back into this+0x2f8
        permanently, because the AI's ShootingSystem may bypass TryUse
        on later shots and read m_ShootDelay directly.

Cave: 0x1FD9D84..0x1FD9E08 (dead DebugLog code, 132 bytes)
"""
import struct, os, hashlib
from capstone import *

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)


def dis(v):
    for i in md.disasm(struct.pack("<I", v), 0):
        return "%s %s" % (i.mnemonic, i.op_str)
    return "?"


def enc_b(at, tgt):
    off = tgt - at
    assert off % 4 == 0
    assert -0x8000000 <= off <= 0x7FFFFFC
    return 0x14000000 | ((off // 4) & 0x3FFFFFF)


def enc_bl(at, tgt):
    return 0x94000000 | (((tgt - at) // 4) & 0x3FFFFFF)


def enc_bcond(cond, at, tgt):
    return 0x54000000 | ((((tgt - at) // 4) & 0x7FFFF) << 5) | cond


def enc_cbz(rt, at, tgt):
    return 0x34000000 | ((((tgt - at) // 4) & 0x7FFFF) << 5) | rt


def enc_cbnz(rt, at, tgt):
    return 0x35000000 | ((((tgt - at) // 4) & 0x7FFFF) << 5) | rt


def enc_adrp(rd, at, tgt):
    imm = ((tgt & ~0xFFF) - (at & ~0xFFF)) >> 12
    imm &= 0x1FFFFF
    return 0x90000000 | ((imm & 0x3) << 29) | (((imm >> 2) & 0x7FFFF) << 5) | rd


def enc_ldr_x(rt, rn, off):
    assert off % 8 == 0
    return 0xF9400000 | ((off // 8) << 10) | (rn << 5) | rt


def enc_str_s(rt, rn, off):
    assert off % 4 == 0
    return 0xBD000000 | ((off // 4) << 10) | (rn << 5) | rt


def enc_ldr_w(rt, rn, off):
    assert off % 4 == 0
    return 0xB9400000 | ((off // 4) << 10) | (rn << 5) | rt


def enc_ldr_s(rt, rn, off):
    assert off % 4 == 0
    return 0xBD400000 | ((off // 4) << 10) | (rn << 5) | rt


def enc_cmp_x(a, b):
    return 0xEB00001F | (b << 16) | (a << 5)


def enc_fmov(sd, imm8):
    return 0x1E200000 | (imm8 << 13) | 0x1000 | sd


def enc_fmul(sd, sn, sm):
    return 0x1E200800 | (sm << 16) | (sn << 5) | sd


CAVE = 0x1FD9D84
LIMIT = 0x1FD9E08
HOOK = 0x200891C
RESUME = 0x2008920
CLSINIT = 0x1808CE4
SYSMGR = 0x3B9A3D0
IMM_05 = 0x60
IMM_40 = 0x10


class C:
    def __init__(s, base):
        s.a = base
        s.it = []
        s.lb = {}

    def w(s, v, d):
        s.it.append((s.a, v, d, None)); s.a += 4

    def ref(s, k, args, d):
        s.it.append((s.a, 0, d, (k, args))); s.a += 4

    def label(s, n):
        s.lb[n] = s.a

    def resolve(s):
        out = []
        for addr, v, d, r in s.it:
            if r is None:
                val = v
            else:
                k, a = r
                if k == 'ldr_s':   val = enc_ldr_s(a[0], a[1], a[2])
                elif k == 'ldr_x': val = enc_ldr_x(a[0], a[1], a[2])
                elif k == 'str_s': val = enc_str_s(a[0], a[1], a[2])
                elif k == 'ldr_w': val = enc_ldr_w(a[0], a[1], a[2])
                elif k == 'cbz':   val = enc_cbz(a[0], addr, s.lb[a[1]])
                elif k == 'cbnz':  val = enc_cbnz(a[0], addr, s.lb[a[1]])
                elif k == 'adrp':  val = enc_adrp(a[0], addr, a[1])
                elif k == 'cmp_x': val = enc_cmp_x(a[0], a[1])
                elif k == 'bcond': val = enc_bcond(a[0], addr, s.lb[a[1]])
                elif k == 'bl':    val = enc_bl(addr, a[0])
                elif k == 'babs':  val = enc_b(addr, a[0])
                else: raise ValueError(k)
            out.append((addr, val, d))
        return out


def build():
    c = C(CAVE)
    c.ref('ldr_s', (9, 19, 0x2f8), "ldr s9,[x19,#0x2f8]     m_ShootDelay")
    c.ref('ldr_x', (21, 19, 0x110), "ldr x21,[x19,#0x110]    Item.m_Character")
    c.ref('cbz', (21, 'ai'), "cbz x21,ai")
    c.ref('adrp', (9, SYSMGR), "adrp x9,#SysMgr")
    c.ref('ldr_x', (9, 9, 0x3d0), "ldr x9,[x9,#0x3d0]")
    c.ref('cbz', (9, 'ai'), "cbz x9,ai")
    c.ref('ldr_w', (10, 9, 0xe0), "ldr w10,[x9,#0xe0]      classinit")
    c.ref('cbnz', (10, 'ci'), "cbnz w10,ci")
    c.ref('bl', (CLSINIT,), "bl classinit")
    c.ref('adrp', (9, SYSMGR), "adrp x9,#SysMgr         reload")
    c.ref('ldr_x', (9, 9, 0x3d0), "ldr x9,[x9,#0x3d0]      reload")
    c.label('ci')
    c.ref('ldr_x', (9, 9, 0x0), "ldr x9,[x9]")
    c.ref('ldr_x', (9, 9, 0xb8), "ldr x9,[x9,#0xb8]       static")
    c.ref('ldr_x', (9, 9, 0x78), "ldr x9,[x9,#0x78]       instance")
    c.ref('cbz', (9, 'ai'), "cbz x9,ai")
    c.ref('ldr_x', (9, 9, 0x368), "ldr x9,[x9,#0x368]      player GO")
    c.ref('cmp_x', (21, 9), "cmp x21,x9")
    c.ref('bcond', (1, 'ai'), "b.ne ai")
    # ---- player ----
    c.w(enc_fmov(16, IMM_05), "fmov s16,#0.5           player")
    c.w(enc_fmul(9, 9, 16), "fmul s9,s9,s16          -> 8x stock")
    c.ref('babs', (RESUME,), "b 0x2008920")
    # ---- AI: restore stock and persist ----
    c.label('ai')
    c.w(enc_fmov(16, IMM_40), "fmov s16,#4.0           AI")
    c.w(enc_fmul(9, 9, 16), "fmul s9,s9,s16          -> 1x stock")
    c.ref('str_s', (9, 19, 0x2f8), "str s9,[x19,#0x2f8]     persist stock delay")
    c.ref('babs', (RESUME,), "b 0x2008920")

    out = c.resolve()
    end = c.a - 4
    assert end <= LIMIT, "overflow 0x%X" % end
    return out, end


def main():
    SRC = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_patched_v85\libil2cpp.so"
    DST = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_patched_v100\libil2cpp.so"
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    d = bytearray(open(SRC, 'rb').read())

    out, end = build()
    print("CAVE 0x%07X..0x%07X  (%d bytes / %d)" % (CAVE, end, end - CAVE + 4, LIMIT - CAVE))
    for addr, v, dsc in out:
        struct.pack_into("<I", d, addr - 0x1000, v)
        print("  0x%07X: 0x%08X  %-26s %s" % (addr, v, dis(v), dsc))

    nb = enc_b(HOOK, CAVE)
    struct.pack_into("<I", d, HOOK - 0x1000, nb)
    print()
    print("HOOK 0x%07X -> b 0x%07X" % (HOOK, CAVE))

    open(DST, 'wb').write(d)
    print()
    print("v100 sha256:", hashlib.sha256(bytes(d)).hexdigest())


if __name__ == "__main__":
    main()
