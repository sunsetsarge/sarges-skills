#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate an image with the ChatGPT desktop app and save it as a PNG.

Sends an image prompt, waits for generation to finish, then right-clicks the
image and uses "Copy image" (selected via keyboard) to pull the FULL-RESOLUTION
bitmap off the clipboard and save it. Falls back to a window screenshot if no
image is found on the clipboard.

Usage:
  python gen_image.py "a red apple on a white background" --out apple.png
  python gen_image.py "Generate an image of a city at night" --raw
  python gen_image.py "logo for a coffee shop" --no-new      # current chat
Options: --timeout <sec>  --ix/--iy <fraction> (image-center target for the
right-click; defaults work for a single generated image).
"""
import sys, os, time, argparse
import pyautogui
from PIL import Image, ImageGrab
from cgpt_common import (find_chatgpt_window, ensure_foreground, window_rect,
                         send_prompt, wait_until_stable, grab_window)

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_WORDS = ('image', 'picture', 'photo', 'draw', 'render', 'illustration',
             'logo', 'icon', 'sprite', 'art', 'paint', 'sketch', 'generate', 'dall')


def extract_image(win, out_path, ix_frac, iy_frac):
    """Right-click the image, choose Copy image (keyboard), grab clipboard, save.
    Returns the saved (w, h) or None if the clipboard held no bitmap."""
    if not ensure_foreground(win):
        return None
    L, T, R, B = window_rect(win)
    W, H = R - L, B - T
    ix, iy = L + int(W * ix_frac), T + int(H * iy_frac)
    pyautogui.rightClick(ix, iy)
    time.sleep(0.7)
    pyautogui.press('down')      # highlight "Copy image"
    time.sleep(0.2)
    pyautogui.press('enter')     # copy to clipboard
    time.sleep(0.9)
    data = ImageGrab.grabclipboard()
    if isinstance(data, Image.Image):
        data.save(out_path)
        return data.size
    pyautogui.press('escape')    # close any stray menu
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prompt')
    ap.add_argument('--out', default=os.path.join(BASE, 'generated.png'))
    ap.add_argument('--no-new', dest='new', action='store_false',
                    help='use the current chat instead of starting a new one')
    ap.add_argument('--raw', action='store_true', help='send the prompt verbatim')
    ap.add_argument('--timeout', type=int, default=220)
    ap.add_argument('--retries', type=int, default=1,
                    help='auto-retry if ChatGPT fails to produce an image')
    ap.add_argument('--ix', type=float, default=0.69, help='image-center x fraction')
    ap.add_argument('--iy', type=float, default=0.45, help='image-center y fraction')
    ap.set_defaults(new=True)
    args = ap.parse_args()

    prompt = args.prompt
    if not args.raw and not any(w in prompt.lower() for w in IMG_WORDS):
        prompt = 'Generate an image: ' + prompt

    win = find_chatgpt_window()
    if not win:
        print('NO_WINDOW')
        return 2
    attempts = max(1, args.retries + 1)
    size, ok, elapsed = None, False, 0
    for i in range(attempts):
        if i == 0:
            sent = send_prompt(win, prompt, new=args.new)
        else:
            print('retry %d/%d (ChatGPT did not return an image)...' % (i, attempts - 1))
            sent = send_prompt(win, 'That image generation failed. Please try '
                               'generating the image again.', new=False)
        if not sent:
            print('SEND_ABORTED: could not secure a stable foreground (busy desktop?).')
            return 3
        ok, elapsed = wait_until_stable(window_rect(win), max_wait=args.timeout)
        time.sleep(1.2)          # let the image settle fully
        size = extract_image(win, args.out, args.ix, args.iy)
        if size:
            break

    grab_window(win, os.path.join(BASE, 'gen_state.png'))   # reference screenshot
    if size:
        print('IMAGE_SAVED out=%s size=%s stable=%s elapsed=%ss'
              % (args.out, size, ok, elapsed))
        return 0
    print('NO_IMAGE after %d attempt(s): ChatGPT may have failed to generate (see '
          'gen_state.png), or the right-click missed the image (try --ix/--iy). '
          'stable=%s elapsed=%ss' % (attempts, ok, elapsed))
    return 4


if __name__ == '__main__':
    sys.exit(main())
