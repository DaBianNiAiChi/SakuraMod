#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""inspect_phdrs.py -- dump the ELF program headers of libil2cpp.so so we can
work out how to extend the executable segment.
"""
import struct, sys

P = r"C:\Users\<USER>\Desktop\Android\SakuraUnpack\_extract\lib\arm64-v8a\libil2cpp.so"
PT = {0: 'NULL', 1: 'LOAD', 2: 'DYNAMIC', 3: 'INTERP', 4: 'NOTE', 6: 'PHDR',
      7: 'TLS', 0x6474E550: 'GNU_EH_FRAME', 0x6474E551: 'GNU_STACK',
      0x6474E552: 'GNU_RELRO', 0x6474E553: 'GNU_PROPERTY'}
PF = {1: 'X', 2: 'W', 4: 'R'}


def main():
    d = open(P, 'rb').read()
    print("file size: %d (0x%X)" % (len(d), len(d)))
    print("magic:", d[:4])
    print("class:", d[4], "(2=ELF64)")
    print("data :", d[5], "(1=LE)")
    e_phoff = struct.unpack_from("<Q", d, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", d, 0x36)[0]
    e_phnum = struct.unpack_from("<H", d, 0x38)[0]
    print("e_phoff=0x%X  e_phentsize=%d  e_phnum=%d" % (e_phoff, e_phentsize, e_phnum))
    print()
    print("%-3s %-18s %-10s %-10s %-10s %-10s %-12s %-8s" %
          ("idx", "type", "flags", "offset", "vaddr", "paddr", "filesz", "memsz"))
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", d, o)[0]
        p_flags = struct.unpack_from("<I", d, o + 4)[0]
        p_offset = struct.unpack_from("<Q", d, o + 8)[0]
        p_vaddr = struct.unpack_from("<Q", d, o + 0x10)[0]
        p_paddr = struct.unpack_from("<Q", d, o + 0x18)[0]
        p_filesz = struct.unpack_from("<Q", d, o + 0x20)[0]
        p_memsz = struct.unpack_from("<Q", d, o + 0x28)[0]
        p_align = struct.unpack_from("<Q", d, o + 0x30)[0]
        fl = ''.join(PF.get(b, '?') for b in (1, 2, 4) if p_flags & b) or '-'
        tn = PT.get(p_type, '0x%X' % p_type)
        print("%-3d %-18s %-10s 0x%08X 0x%08X 0x%08X 0x%08X 0x%08X  align=0x%X" %
              (i, tn, fl, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align))

    # section headers
    e_shoff = struct.unpack_from("<Q", d, 0x28)[0]
    e_shentsize = struct.unpack_from("<H", d, 0x3A)[0]
    e_shnum = struct.unpack_from("<H", d, 0x3C)[0]
    e_shstrndx = struct.unpack_from("<H", d, 0x3E)[0]
    shstr_off = struct.unpack_from("<Q", d, e_shoff + e_shstrndx * e_shentsize + 0x18)[0]

    def nm(off):
        end = d.index(b'\0', off)
        return d[off:end].decode('ascii', 'replace')

    print()
    print("section headers: e_shoff=0x%X  e_shnum=%d" % (e_shoff, e_shnum))
    print("%-3s %-22s %-11s %-11s %-11s" % ("idx", "name", "addr", "offset", "size"))
    for i in range(e_shnum):
        b = e_shoff + i * e_shentsize
        n = nm(shstr_off + struct.unpack_from("<I", d, b)[0])
        addr = struct.unpack_from("<Q", d, b + 0x10)[0]
        off = struct.unpack_from("<Q", d, b + 0x18)[0]
        sz = struct.unpack_from("<Q", d, b + 0x20)[0]
        print("%-3d %-22s 0x%08X 0x%08X 0x%08X" % (i, n[:22], addr, off, sz))


if __name__ == "__main__":
    main()
