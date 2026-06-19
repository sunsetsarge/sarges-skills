#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ask the ChatGPT Windows desktop app a question and capture its reply.

The app is Chromium-based and hides its web content from UI Automation, so we
drive it like a human: focus the window, paste the prompt into the composer,
press Enter, wait for the reply to stop changing, and screenshot the result.

Usage:
  python ask_chatgpt.py "your question"
  python ask_chatgpt.py "your question" --new          # start a fresh chat first
  python ask_chatgpt.py "your question" --no-send       # type but don't submit (debug)
  python ask_chatgpt.py "your question" --out reply.png --timeout 150
"""
import sys, os, time, argparse
import pyautogui, pyperclip
from PIL import ImageGrab
from cgpt_common import (find_chatgpt_window, grab_window, window_rect,
                         focus_window, is_foreground, capture_full_reply)

pyautogui.FAILSAFE = True   # slam mouse into a screen corner to abort
pyautogui.PAUSE = 0.10

BASE = os.path.dirname(os.path.abspath(__file__))


def _small_signature(bbox):
    """Tiny grayscale fingerprint of the *inner conversation area* for change
    detection. Excludes the sidebar (left), title bar (top), the window's right
    edge (where windows behind can bleed through), and the composer (bottom,
    which has a blinking caret) so only real reply changes register."""
    img = ImageGrab.grab(bbox=bbox, all_screens=True).convert('L')
    w, h = img.size
    inner = img.crop((int(w * 0.22), int(h * 0.08), int(w * 0.97), int(h * 0.86)))
    return list(inner.resize((80, 64)).getdata())


def wait_until_stable(bbox, max_wait=150, settle=2.5, poll=1.0, start_delay=1.5):
    """Block until the window stops changing (reply finished streaming)."""
    time.sleep(start_delay)
    prev = _small_signature(bbox)
    changed_once = False
    stable_since = None
    t0 = time.time()
    while time.time() - t0 < max_wait:
        time.sleep(poll)
        cur = _small_signature(bbox)
        diff = sum(1 for a, b in zip(prev, cur) if abs(a - b) > 12)
        prev = cur
        if diff > 15:
            changed_once = True
            stable_since = None
        elif changed_once:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= settle:
                return True, round(time.time() - t0, 1)
    return False, round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('question', nargs='?', default='Reply with exactly: BRIDGE OK')
    ap.add_argument('--new', action='store_true', help='start a new chat first (Ctrl+N)')
    ap.add_argument('--no-send', action='store_true', help='type but do not press Enter')
    ap.add_argument('--click', action='store_true',
                    help='click the bottom composer before typing (for active chats '
                         'where auto-focus may not hold)')
    ap.add_argument('--out', default=BASE + r'\answer.png')
    ap.add_argument('--full', action='store_true',
                    help='scroll-and-stitch the whole reply into one tall PNG')
    ap.add_argument('--full-debug', action='store_true', help='verbose scroll logging')
    ap.add_argument('--timeout', type=int, default=150)
    ap.add_argument('--x-frac', type=float, default=0.50)
    ap.add_argument('--y-frac', type=float, default=0.935)
    args = ap.parse_args()

    win = find_chatgpt_window()
    if not win:
        print('NO_WINDOW')
        return 2

    if not focus_window(win):
        print('NOT_FOREGROUND: could not bring ChatGPT to front; aborting to avoid '
              'typing into the wrong window.')
        return 3
    time.sleep(0.4)

    def guard(where):
        """Require a STABLE foreground before any keystroke, so Ctrl+N / paste
        can't leak into another app (which would e.g. open a File Explorer)."""
        for _ in range(4):
            if is_foreground(win):
                time.sleep(0.15)
                if is_foreground(win):     # still foreground a beat later
                    return True
            focus_window(win)
            time.sleep(0.3)
        print('NOT_FOREGROUND before %s; aborting (busy desktop stole focus).' % where)
        return False

    if args.new:
        if not guard('new-chat'):
            return 3
        pyautogui.hotkey('ctrl', 'n')
        time.sleep(1.2)

    L, T, R, B = window_rect(win)
    cx = L + int((R - L) * args.x_frac)
    cy = T + int((B - T) * args.y_frac)

    if not guard('typing'):
        return 3
    # On a new/active chat ChatGPT auto-focuses the composer, so a click is
    # usually unnecessary (and on an empty new chat the composer is centered,
    # not at the bottom). Clicking is opt-in for stubborn active chats.
    if args.click:
        pyautogui.click(cx, cy)
        time.sleep(0.3)
    # Clear any existing draft in the (focused) composer.
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('delete')
    time.sleep(0.15)

    # Paste the prompt (handles unicode / long text; restore clipboard after).
    saved_clip = ''
    try:
        saved_clip = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(args.question)
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.4)

    if args.no_send:
        path, size, bb = grab_window(win, BASE + r'\composer_check.png')
        print('TYPED_NO_SEND click=(%d,%d) saved=%s size=%s' % (cx, cy, path, size))
        return 0

    if not guard('send'):
        return 3
    pyautogui.press('enter')
    ok, elapsed = wait_until_stable((L, T, R, B), max_wait=args.timeout)

    # Restore the user's clipboard.
    try:
        pyperclip.copy(saved_clip)
    except Exception:
        pass

    if args.full:
        path, size, n = capture_full_reply(win, args.out, debug=args.full_debug)
        print('SENT stable=%s elapsed=%ss full=%s size=%s frames=%d'
              % (ok, elapsed, path, size, n))
    else:
        path, size, bb = grab_window(win, args.out)
        print('SENT stable=%s elapsed=%ss saved=%s size=%s' % (ok, elapsed, path, size))
    return 0


if __name__ == '__main__':
    sys.exit(main())
