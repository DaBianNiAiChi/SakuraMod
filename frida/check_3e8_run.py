#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_3e8_run.py"""
import os, sys, json, time, argparse
import frida

ROOT = r'C:\Users\<USER>\Desktop\Android\SakuraUnpack'
JS = os.path.join(ROOT, '_tools', 'frida', 'check_3e8.js')
PKG = 'SakuraSimulator'

ap = argparse.ArgumentParser()
ap.add_argument('--serial', default='<YOUR_DEVICE_SERIAL>')
ap.add_argument('--seconds', type=float, default=130.0)
args = ap.parse_args()


def on_msg(m, d):
    if m.get('type') != 'send':
        print('[err]', json.dumps(m)[:250], flush=True)
        return
    print(json.dumps(m.get('payload'), ensure_ascii=False)[:500], flush=True)


def main():
    dev = frida.get_device(args.serial)
    procs = [p for p in dev.enumerate_processes() if p.name == PKG]
    if not procs:
        print('GAME NOT RUNNING')
        return 1
    pid = procs[0].pid
    print('[3e8] attach pid=%d' % pid)
    s = dev.attach(pid)
    sc = s.create_script(open(JS, encoding='utf-8').read())
    sc.on('message', on_msg)
    sc.load()
    print('[3e8] armed; PLAYER fire then NPC fire')
    time.sleep(args.seconds)
    try:
        sc.unload()
    except Exception:
        pass
    try:
        s.detach()
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
