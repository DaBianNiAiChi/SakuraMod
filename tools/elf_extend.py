#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""elf_extend.py -- add a brand-new executable PT_LOAD segment to libil2cpp.so.

Why
---
The binary has no usable code caves larger than 128 bytes, which makes every
non-trivial trampoline impossible.  Instead of hunting for caves we append a
fresh page of code at the end of the file and map it as a new PT_LOAD segment.

How
---
    1. Append CODE_SIZE bytes at file offset APPEND_OFF (4 KiB aligned).
    2. Write an 11th program header at 0x270 describing it.
    3. Bump e_phnum from 10 to 11.
    4. Shrink the PT_NOTE entry so it only covers .note.gnu.build-id
       (the Android ident note at 0x270 is overwritten by the new phdr,
        which is harmless).

Result
------
    New executable segment at vaddr 0x4040000, file offset 0x3E07000,
    size 0x1000.  Branch range from .text (±128 MiB) is well within limits.

Usage
-----
    python elf_extend.py <src.so> <dst.so> <code.bin>
    python elf_extend.py --info <so>
"""
import struct, sys, os

NEW_VADDR = None      # computed as append_off + 0x1000
NEW_ALIGN = 0x1000
CODE_SIZE = 0x1000

PT_LOAD = 1
PT_NOTE = 4
PF_X, PF_W, PF_R = 1, 2, 4


def read_elf(path):
    return bytearray(open(path, 'rb').read())


def hdr(d):
    e_phoff = struct.unpack_from("<Q", d, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", d, 0x36)[0]
    e_phnum = struct.unpack_from("<H", d, 0x38)[0]
    return e_phoff, e_phentsize, e_phnum


def info(path):
    d = read_elf(path)
    off, esz, num = hdr(d)
    print("file size   : 0x%X (%d)" % (len(d), len(d)))
    print("e_phoff     : 0x%X" % off)
    print("e_phentsize : %d (0x%X)" % (esz, esz))
    print("e_phnum     : %d" % num)
    print("phdr table  : 0x%X .. 0x%X" % (off, off + esz * num))
    print("phdr+1 ends : 0x%X" % (off + esz * (num + 1)))
    print()
    for i in range(num):
        o = off + i * esz
        t = struct.unpack_from("<I", d, o)[0]
        f = struct.unpack_from("<I", d, o + 4)[0]
        po = struct.unpack_from("<Q", d, o + 8)[0]
        pv = struct.unpack_from("<Q", d, o + 0x10)[0]
        fs = struct.unpack_from("<Q", d, o + 0x20)[0]
        ms = struct.unpack_from("<Q", d, o + 0x28)[0]
        al = struct.unpack_from("<Q", d, o + 0x30)[0]
        print("ph[%2d] type=%-2d flags=%d offset=0x%08X vaddr=0x%08X filesz=0x%08X memsz=0x%08X align=0x%X"
              % (i, t, f, po, pv, fs, ms, al))


def extend(src, dst, code_path):
    d = read_elf(src)
    off, esz, num = hdr(d)

    # ---- checks ----
    need = off + esz * (num + 1)
    print("phdr table will need up to 0x%X" % need)
    # PT_NOTE currently starts at 0x270; build-id starts at 0x308
    note_idx = None
    for i in range(num):
        o = off + i * esz
        if struct.unpack_from("<I", d, o)[0] == PT_NOTE:
            note_idx = i
            break
    assert note_idx is not None, "no PT_NOTE"
    no = off + note_idx * esz
    p_off = struct.unpack_from("<Q", d, no + 8)[0]
    p_fsz = struct.unpack_from("<Q", d, no + 0x20)[0]
    print("PT_NOTE at ph[%d]: offset=0x%X filesz=0x%X" % (note_idx, p_off, p_fsz))

    code = open(code_path, 'rb').read()
    assert len(code) <= CODE_SIZE, "code too big"
    print("code: %d bytes" % len(code))

    # ---- append the code page ----
    append_off = (len(d) + NEW_ALIGN - 1) & ~(NEW_ALIGN - 1)
    d += b'\0' * (append_off - len(d))
    d += code
    d += b'\0' * (CODE_SIZE - len(code))
    new_vaddr = append_off + 0x1000
    print("appended at file offset 0x%X, vaddr 0x%X" % (append_off, new_vaddr))
    assert append_off % NEW_ALIGN == 0

    # ---- write the new program header ----
    ph = bytearray(esz)
    struct.pack_into("<I", ph, 0x00, PT_LOAD)
    struct.pack_into("<I", ph, 0x04, PF_R | PF_X)
    struct.pack_into("<Q", ph, 0x08, append_off)
    struct.pack_into("<Q", ph, 0x10, new_vaddr)
    struct.pack_into("<Q", ph, 0x18, new_vaddr)
    struct.pack_into("<Q", ph, 0x20, CODE_SIZE)
    struct.pack_into("<Q", ph, 0x28, CODE_SIZE)
    struct.pack_into("<Q", ph, 0x30, NEW_ALIGN)
    new_ph_off = off + esz * num
    d[new_ph_off:new_ph_off + esz] = ph
    print("new phdr written at 0x%X" % new_ph_off)

    # ---- bump e_phnum ----
    struct.pack_into("<H", d, 0x38, num + 1)
    print("e_phnum: %d -> %d" % (num, num + 1))

    # ---- shrink PT_NOTE to only cover .note.gnu.build-id (offset 0x308) ----
    struct.pack_into("<Q", d, no + 0x08, 0x308)   # p_offset
    struct.pack_into("<Q", d, no + 0x10, 0x308)   # p_vaddr
    struct.pack_into("<Q", d, no + 0x18, 0x308)   # p_paddr
    struct.pack_into("<Q", d, no + 0x20, 0x18)    # p_filesz
    struct.pack_into("<Q", d, no + 0x28, 0x18)    # p_memsz
    print("PT_NOTE trimmed to 0x308..0x320 (build-id only)")

    open(dst, 'wb').write(d)
    print()
    print("written:", dst, "size=0x%X" % len(d))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    if sys.argv[1] == '--info':
        info(sys.argv[2])
        return 0
    if len(sys.argv) != 4:
        print(__doc__)
        return 1
    extend(sys.argv[1], sys.argv[2], sys.argv[3])
    return 0


if __name__ == '__main__':
    sys.exit(main())
