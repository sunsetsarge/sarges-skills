#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focus the ChatGPT window and save a screenshot of it.
Usage: python shot.py [output.png]"""
import sys, os, time
from cgpt_common import find_chatgpt_window, grab_window

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shot.png')

win = find_chatgpt_window()
if not win:
    print('NO_WINDOW')
    sys.exit(2)
try:
    win.set_focus()
except Exception as e:
    print('FOCUS_WARN', e)
time.sleep(0.5)
path, size, bbox = grab_window(win, OUT)
print('SAVED', path, 'size', size, 'rect', bbox)
