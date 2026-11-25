#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_v115.py -- v115 = v100 + force FriendlyFire ON.

Background
----------
The game ships a setting "开启误射" (friendly fire).  When it is off the
player's projectiles can only damage objects whose Unity Tag matches
Projectile.seekTag (+0xC0), which in practice means only the tagged enemies.

The flag lives in:
    SaveGameManager.FriendlyFire   static bool, static_fields + 0x10
and is set to true by:
    SaveGameManager.FriendlyFireON()  RVA 0x1F2734C
        ...
        0x1F273BC: ldr  x8,[x0,#0xb8]     ; static_fields
        0x1F273C8: mov  w9,#1
        0x1F273CC: strb w9,[x8,#0x10]     ; FriendlyFire = true
        ...
        0x1F273D4: b    <tail call>

The cleanest place to force it is inside SaveGameManager.Start (0x1E30548),
which runs once per game load.  We append a small stub to the free cave at
0x1FD9E0C (44 bytes, currently used by the v85 money cave... no: the money
cave is 0x1FD9E0C..0x1FD9E38 in v85 and is still live in v100).

Instead we hook the START of SaveGameManager.Start with a trampoline into the
free 32-byte block at 0x1FD9DE8 (currently NOP padding in v114 lineage) --
but v100 does not use 0x1FD9DE8, it uses up to 0x1FD9DE4.  So 0x1FD9DE8..0x1FD9E08
is free in v100 (32 bytes).

Stub (8 instructions):
    adrp x8,#SaveGameManagerClassSlot
    ldr  x8,[x8,#off]
    cbz  x8,out
    ldr  x9,[x8]                 ; class object
    cbz  x9,out
    ldr  x8,[x9,#0xb8]           ; static_fields
    mov  w9,#1
    strb w9,[x8,#0x10]           ; FriendlyFire = true
out:
    <original first instruction of Start>

That is 9 instructions = 36 bytes, which does NOT fit in 32.

Alternative: hook a point INSIDE Start after the classinit guard, where x8
already holds something useful.  Look at 0x1E305C0:
    0x1E305C0: mov  w8,#1
    0x1E305C4: strb w8,[x20,#0x10]    ; x20 = 0x1FDB000 page +0x10  <- this is
                                      ; the classinit "already ran" flag for
                                      ; SaveGameManager itself!
Right after that we know static_fields exists.  But we still need its address.

Simplest reliable approach: call FriendlyFireON() is an instance method and we
are inside Start where x19 == this.  So the stub only needs:
    mov x0, x19
    ... but we must preserve x19 and lr and all caller-saved regs.

That needs a proper trampoline with stp/ldp:

    stp x19,x30,[sp,#-0x10]!     ; save
    mov x0, x19
    bl  0x1F2734C                ; FriendlyFireON()
    ldp x19,x30,[sp],#0x10       ; restore
    <original instruction at hook site>
    b   <hook+4>

That is 5 instructions = 20 bytes -> fits in the 32-byte block.

Hook site: 0x1E305C8 (right after the strb, where x19 is still this and the
SaveGameManager is fully initialised).
"""
import struct, os, hashlib
from capstone import *

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

BASE = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_KEEP\Sakura_v100-aligned-debugSigned.apk"
PATCHED = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_KEEP\_v100_extracted\libil2cpp.so"
DST_DIR = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_patched_v115"
DST = os.path.join(DST_DIR, "libil2cpp.so")

CAVE = 0x1FD9DE8
CAVE_END = 0x1FD9E08
HOOK = 0x1E305C8
FRIENDLY_FIRE_ON = 0x1F2734C
V100_SHA = "aeac29ca07c4781ca46371b7204417bc8f90b81c852241716f91a9ca118d48f5"


def dis(v):
    for i in md.disasm(struct.pack("<I", v), 0):
        return "%s %s" % (i.mnemonic, i.op_str)
    return "?"


def eb(at, tgt):
    off = tgt - at
    assert off % 4 == 0
    assert -0x8000000 <= off <= 0x7FFFFFC, "b range %d" % off
    return 0x14000000 | ((off // 4) & 0x3FFFFFF)


def ebl(at, tgt):
    return 0x94000000 | (((tgt - at) // 4) & 0x3FFFFFF)


def main():
    os.makedirs(DST_DIR, exist_ok=True)
    d = bytearray(open(PATCHED, 'rb').read())
    h = hashlib.sha256(bytes(d)).hexdigest()
    assert h == V100_SHA, "not v100 (got %s)" % h
    print("base = v100 OK")

    # verify the hook site is the expected instruction
    cur = struct.unpack_from("<I", d, HOOK - 0x1000)[0]
    print("hook site 0x%07X: %s" % (HOOK, dis(cur)))
    assert cur == 0xD000EB55, "expected adrp x21 at 0x1E305C8, got 0x%08X" % cur

    # ---- build the stub at the cave ----
    a = CAVE
    words = []
    words.append((a, 0xA9BF7BF3, "stp x19,x30,[sp,#-0x10]!")); a += 4
    words.append((a, 0xAA1303E0, "mov x0,x19")); a += 4
    words.append((a, ebl(a, FRIENDLY_FIRE_ON), "bl FriendlyFireON()")); a += 4
    words.append((a, 0xA8C17BF3, "ldp x19,x30,[sp],#0x10")); a += 4
    # original instruction that we displaced
    words.append((a, cur, "original: %s" % dis(cur))); a += 4
    words.append((a, eb(a, HOOK + 4), "b 0x%X" % (HOOK + 4))); a += 4

    print()
    print("== stub 0x%07X..0x%07X (%d / %d) ==" % (CAVE, a - 4, a - CAVE, CAVE_END - CAVE))
    assert a <= CAVE_END, "cave overflow"
    for addr, w, desc in words:
        struct.pack_into("<I", d, addr - 0x1000, w)
        print("  0x%07X: 0x%08X  %-26s %s" % (addr, w, dis(w), desc))

    # pad
    for rva in range(a, CAVE_END, 4):
        struct.pack_into("<I", d, rva - 0x1000, 0xD503201F)

    # install the hook
    new = eb(HOOK, CAVE)
    struct.pack_into("<I", d, HOOK - 0x1000, new)
    print()
    print("HOOK 0x%07X -> b 0x%07X" % (HOOK, CAVE))

    open(DST, 'wb').write(d)
    print()
    print("v115 sha256:", hashlib.sha256(bytes(d)).hexdigest())

    # ---- static verification ----
    print()
    print("=" * 70)
    print("VERIFY")
    print("=" * 70)
    for addr, w, _ in words:
        got = struct.unpack_from("<I", d, addr - 0x1000)[0]
        assert got == w, "mismatch at 0x%X" % addr
    print("stub bytes written OK")
    got = struct.unpack_from("<I", d, HOOK - 0x1000)[0]
    print("hook word: 0x%08X  %s" % (got, dis(got)))


if __name__ == "__main__":
    main()
