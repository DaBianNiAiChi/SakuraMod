#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_v116.py -- v116: force FriendlyFire = true by writing the static
field directly, without calling FriendlyFireON().

v115 crashed at 0x1E30608 (inside SaveGameManager.Start) because
FriendlyFireON() ends in a tail call and clobbered registers that Start
still needed.

v116 writes the flag inline instead.  From FriendlyFireON's disassembly:

    0x1F273A8: ldr  x0,[x20]          ; x20 = class pointer slot 0x1C73A38
    0x1F273AC: ldr  w8,[x0,#0xe0]     ; classinit guard
    0x1F273B0: cbnz w8, +0xc
    0x1F273B4: bl   classinit
    0x1F273B8: ldr  x0,[x20]          ; reload
    0x1F273BC: ldr  x8,[x0,#0xb8]     ; static_fields
    0x1F273CC: strb w9,[x8,#0x10]     ; FriendlyFire = true

Stub placed at 0x1FD9DE8 (32 bytes free):

    adrp x8,#0x1c73000
    ldr  x8,[x8,#0xa38]      ; class slot
    cbz  x8,out
    ldr  x8,[x8]             ; class object
    cbz  x8,out
    ldr  x8,[x8,#0xb8]       ; static_fields (may be null before classinit,
                             ;  but SaveGameManager.Start runs after Awake so
                             ;  it is initialised)
    cbz  x8,out
    mov  w9,#1
    strb w9,[x8,#0x10]       ; FriendlyFire = true
out: <original insn>         ; 9 insns = 36 bytes -> does not fit in 32

So we use a second free block: 0x1FD9E0C is the v85/v100 money cave and is in
use.  Instead reuse the first free block at 0x1FD9D84?  No - that is the
fire-rate cave.

Better: use the 40-byte cave at 0x1FD9D5C that v100 uses for bullet speed...
also in use.

Available in v100:
  0x1FD9DE8..0x1FD9E08   32 bytes  (free)
That is the only free block.  9 instructions do not fit.

Solution: split into two jumps through the same 32-byte block is not possible.

So: hook ONE instruction that already has a valid x8 = class slot?  No.

Alternative: hook at 0x1E305C0 where the code does
    0x1E305C0: mov  w8,#1
    0x1E305C4: strb w8,[x20,#0x10]    ; x20 = 0x1FDB000 + 0x10
That x20 is a DIFFERENT class's init flag.

Cleanest: replace the ENTIRE free block with a shorter stub that only needs
to store 1 into the static field, accepting that we call the classinit-free
path.  Instructions:

    adrp x8,#0x1c73000       1
    ldr  x8,[x8,#0xa38]      2
    ldr  x8,[x8]             3
    ldr  x8,[x8,#0xb8]       4   (static fields)
    mov  w9,#1               5
    strb w9,[x8,#0x10]       6   FriendlyFire = 1
    <original insn>          7
    b    back                8   -> 32 bytes exactly

Risk: if static_fields is null this faults.  SaveGameManager.Start runs after
Awake/classinit, so static_fields is guaranteed non-null there.  Verified by
the fact that FriendlyFireON itself does the same [x0,#0xb8] load with no
null check.

That fits exactly in 32 bytes.  8 instructions.
"""
import struct, os, hashlib
from capstone import *

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

PATCHED = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_KEEP\_v100_extracted\libil2cpp.so"
DST_DIR = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_patched_v116"
DST = os.path.join(DST_DIR, "libil2cpp.so")

CAVE = 0x1FD9DE8
CAVE_END = 0x1FD9E08
HOOK = 0x1E305C8
CLS_SLOT = 0x3B9AA38
V100_SHA = "aeac29ca07c4781ca46371b7204417bc8f90b81c852241716f91a9ca118d48f5"


def dis(v):
    for i in md.disasm(struct.pack("<I", v), 0):
        return "%s %s" % (i.mnemonic, i.op_str)
    return "?"


def eb(at, tgt):
    off = tgt - at
    assert off % 4 == 0
    assert -0x8000000 <= off <= 0x7FFFFFC
    return 0x14000000 | ((off // 4) & 0x3FFFFFF)


def eadrp(rd, at, tgt):
    imm = ((tgt & ~0xFFF) - (at & ~0xFFF)) >> 12
    imm &= 0x1FFFFF
    return 0x90000000 | ((imm & 0x3) << 29) | (((imm >> 2) & 0x7FFFF) << 5) | rd


def eldrx(rt, rn, off):
    assert off % 8 == 0
    return 0xF9400000 | ((off // 8) << 10) | (rn << 5) | rt


def estrb(rt, rn, off):
    assert 0 <= off <= 0xFFF
    return 0x39000000 | (off << 10) | (rn << 5) | rt


def emov_w(rd, imm16):
    return 0x52800000 | ((imm16 & 0xFFFF) << 5) | rd


def main():
    os.makedirs(DST_DIR, exist_ok=True)
    d = bytearray(open(PATCHED, 'rb').read())
    h = hashlib.sha256(bytes(d)).hexdigest()
    assert h == V100_SHA, "not v100 (got %s)" % h
    print("base = v100 OK")

    cur = struct.unpack_from("<I", d, HOOK - 0x1000)[0]
    print("hook 0x%07X: %s" % (HOOK, dis(cur)))
    assert cur == 0xD000EB55

    a = CAVE
    words = []
    words.append((a, eadrp(8, a, CLS_SLOT), "adrp x8,#SGM class slot")); a += 4
    words.append((a, eldrx(8, 8, CLS_SLOT & 0xFFF), "ldr x8,[x8,#0xa38] slot 0x3B9AA38")); a += 4
    words.append((a, eldrx(8, 8, 0), "ldr x8,[x8]        class obj")); a += 4
    words.append((a, eldrx(8, 8, 0xB8), "ldr x8,[x8,#0xb8]  static_fields")); a += 4
    words.append((a, emov_w(9, 1), "mov w9,#1")); a += 4
    words.append((a, estrb(9, 8, 0x10), "strb w9,[x8,#0x10] FriendlyFire=1")); a += 4
    words.append((a, cur, "orig: %s" % dis(cur))); a += 4
    words.append((a, eb(a, HOOK + 4), "b 0x%X" % (HOOK + 4))); a += 4

    print()
    print("== stub 0x%07X..0x%07X (%d / %d) ==" % (CAVE, a - 4, a - CAVE, CAVE_END - CAVE))
    assert a <= CAVE_END, "overflow"
    for addr, w, desc in words:
        struct.pack_into("<I", d, addr - 0x1000, w)
        print("  0x%07X: 0x%08X  %-26s %s" % (addr, w, dis(w), desc))

    for rva in range(a, CAVE_END, 4):
        struct.pack_into("<I", d, rva - 0x1000, 0xD503201F)

    struct.pack_into("<I", d, HOOK - 0x1000, eb(HOOK, CAVE))
    print()
    print("HOOK 0x%07X -> b 0x%07X" % (HOOK, CAVE))

    open(DST, 'wb').write(d)
    print()
    print("v116 sha256:", hashlib.sha256(bytes(d)).hexdigest())


if __name__ == "__main__":
    main()
