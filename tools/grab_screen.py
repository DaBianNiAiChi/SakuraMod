#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""grab_screen.py -- pull one screenshot from a connected Android device.

Usage:
    python grab_screen.py <serial> [output_path]

The device serial can be found with `adb devices`.
"""
import subprocess
import sys
import os


def main():
    if len(sys.argv) < 2:
        print("usage: python grab_screen.py <serial> [output_path]")
        print("       <serial> from `adb devices`")
        return 1

    serial = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "screenshot.png"

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print("device:", serial)
    print("output:", out_path)

    with open(out_path, "wb") as f:
        p = subprocess.Popen(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            stdout=f,
            stderr=subprocess.PIPE,
        )
        _, err = p.communicate(timeout=120)

    size = os.path.getsize(out_path)
    print("saved:", size, "bytes")
    if err:
        print("stderr:", err[:300])
    if size < 1000:
        print("WARNING: file too small, check the device connection")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
