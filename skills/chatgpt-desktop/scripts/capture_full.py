#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scroll-and-stitch the CURRENT ChatGPT reply into one tall PNG.
Usage: python capture_full.py [out.png] [--scroll N] [--frames N] [--debug]"""
import sys, os, time, argparse
import win32gui
from cgpt_common import find_chatgpt_window, focus_window, capture_full_reply, _win_handle

BASE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument('out', nargs='?', default=BASE + r'\full.png')
ap.add_argument('--notches', type=int, default=2, help='wheel notches up per frame')
ap.add_argument('--frames', type=int, default=24)
ap.add_argument('--width', type=int, help='resize window width before capture (debug)')
ap.add_argument('--height', type=int, help='resize window height before capture (debug)')
ap.add_argument('--debug', action='store_true')
args = ap.parse_args()

win = find_chatgpt_window()
if not win:
    print('NO_WINDOW')
    sys.exit(2)
if not focus_window(win):
    print('NOT_FOREGROUND')
    sys.exit(3)
time.sleep(0.4)
if args.width and args.height:
    l, t, r, b = win32gui.GetWindowRect(_win_handle(win))
    win32gui.SetWindowPos(_win_handle(win), 0, l, t, args.width, args.height, 0x0004)  # SWP_NOZORDER
    time.sleep(0.5)
    print('resized to', args.width, args.height)
path, size, n = capture_full_reply(win, args.out, max_frames=args.frames,
                                   step_notches=args.notches, debug=args.debug)
print('STITCHED saved=%s size=%s frames=%d' % (path, size, n))
