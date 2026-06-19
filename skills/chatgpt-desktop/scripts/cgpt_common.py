#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for driving the ChatGPT Windows desktop app.

The ChatGPT app is Chromium-based and does not expose its web content via
UI Automation, so we treat it as an opaque window: focus it, send keystrokes
with pyautogui, and read responses from screenshots.
"""
import ctypes

# Make the process DPI-aware FIRST so window rects (pywinauto), screen capture
# (PIL ImageGrab) and synthetic input (pyautogui) all share physical pixels.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import sys, io, time
from ctypes import wintypes

# UTF-8 stdout so emoji / unicode in responses don't crash printing.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pywinauto import Desktop
from PIL import ImageGrab

# --- Map a window's PID to its executable path (robust to title changes) ---
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def _pid_exe(pid):
    if not pid:
        return ''
    h = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return ''
    try:
        size = wintypes.DWORD(4096)
        buf = ctypes.create_unicode_buffer(size.value)
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ''
    finally:
        _kernel32.CloseHandle(h)


def find_chatgpt_window(timeout=12.0):
    """Return the top-level ChatGPT app window (pywinauto wrapper) or None.

    Identifies the window by its owning process executable (ChatGPT.exe) rather
    than its title, because the app renames its window to the conversation name.
    """
    deadline = time.time() + timeout
    while True:
        try:
            try:
                fg = win32gui.GetForegroundWindow() if win32gui else None
            except Exception:
                fg = None
            matches = []
            for w in Desktop(backend='uia').windows():
                try:
                    pid = w.element_info.process_id
                except Exception:
                    pid = None
                if not _pid_exe(pid).lower().endswith('chatgpt.exe'):
                    continue
                r = w.element_info.rectangle
                if (r.right - r.left) > 100 and (r.bottom - r.top) > 100:
                    matches.append(w)
            if matches:
                # Prefer the foreground ChatGPT window if multiple are open.
                if fg:
                    for w in matches:
                        try:
                            if _win_handle(w) == fg:
                                return w
                        except Exception:
                            pass
                return matches[0]
        except Exception:
            pass
        if time.time() >= deadline:
            return None
        time.sleep(0.5)


try:
    import win32gui, win32con, win32api
except Exception:
    win32gui = None
    win32con = None
    win32api = None

_VK_MENU = 0x12          # ALT
_KEYEVENTF_KEYUP = 0x0002


def _win_handle(win):
    return getattr(win, 'handle', None) or win.element_info.handle


def is_foreground(win):
    """True iff the given window is the current foreground window."""
    if not win32gui:
        return None
    try:
        return win32gui.GetForegroundWindow() == _win_handle(win)
    except Exception:
        return None


def _alt_unlock():
    """Tap ALT to lift Windows' foreground lock so SetForegroundWindow works
    when called from a background process."""
    if not win32api:
        return
    try:
        win32api.keybd_event(_VK_MENU, 0, 0, 0)
        win32api.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


def focus_window(win, tries=8):
    """Force the window to the foreground. Returns True ONLY if foreground is
    verified, else False. Callers must treat False as 'do not send keystrokes'
    so input can never leak into the wrong window."""
    if not win32gui:
        # Best effort without win32; can't verify, so be conservative.
        try:
            win.set_focus()
        except Exception:
            pass
        return False
    hwnd = _win_handle(win)
    for i in range(tries):
        _alt_unlock()
        try:
            win.set_focus()
        except Exception:
            pass
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.3)
        try:
            if win32gui.GetForegroundWindow() == hwnd:
                return True
        except Exception:
            pass
        # Halfway through, try the minimize/restore toggle which reliably
        # re-asserts foreground for stubborn windows.
        if i == tries // 2:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                time.sleep(0.2)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
            except Exception:
                pass
    try:
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def window_rect(win):
    r = win.element_info.rectangle
    return (r.left, r.top, r.right, r.bottom)


def grab_window(win, path):
    """Save a PNG screenshot of just the given window. Returns (path, size)."""
    bbox = window_rect(win)
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    img.save(path)
    return path, img.size, bbox


# --- Sending prompts & waiting for replies (shared by ask + gen_image) ---
import pyautogui as _pg
import pyperclip as _clip


def ensure_foreground(win, tries=4):
    """Require a STABLE foreground (True) so keystrokes can't leak to another app."""
    for _ in range(tries):
        if is_foreground(win):
            time.sleep(0.15)
            if is_foreground(win):
                return True
        focus_window(win)
        time.sleep(0.3)
    return is_foreground(win) is True


def _stable_sig(bbox):
    img = ImageGrab.grab(bbox=bbox, all_screens=True).convert('L')
    w, h = img.size
    inner = img.crop((int(w * 0.22), int(h * 0.08), int(w * 0.97), int(h * 0.86)))
    return list(inner.resize((80, 64)).getdata())


def wait_until_stable(bbox, max_wait=180, settle=2.5, poll=1.0, start_delay=1.5):
    """Block until the inner conversation area stops changing (reply finished)."""
    time.sleep(start_delay)
    prev = _stable_sig(bbox)
    changed_once, stable_since, t0 = False, None, time.time()
    while time.time() - t0 < max_wait:
        time.sleep(poll)
        cur = _stable_sig(bbox)
        diff = sum(1 for a, b in zip(prev, cur) if abs(a - b) > 12)
        prev = cur
        if diff > 15:
            changed_once, stable_since = True, None
        elif changed_once:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= settle:
                return True, round(time.time() - t0, 1)
    return False, round(time.time() - t0, 1)


def send_prompt(win, text, new=False, click=False, x_frac=0.50, y_frac=0.935):
    """Focus, optionally start a new chat, paste `text` into the composer, Enter.
    Returns True on success, False if a stable foreground couldn't be secured."""
    if not ensure_foreground(win):
        return False
    if new:
        _pg.hotkey('ctrl', 'n')
        time.sleep(1.2)
    L, T, R, B = window_rect(win)
    cx, cy = L + int((R - L) * x_frac), T + int((B - T) * y_frac)
    if not ensure_foreground(win):
        return False
    if click:
        _pg.click(cx, cy)
        time.sleep(0.3)
    _pg.hotkey('ctrl', 'a')
    _pg.press('delete')
    time.sleep(0.15)
    saved = ''
    try:
        saved = _clip.paste()
    except Exception:
        pass
    _clip.copy(text)
    time.sleep(0.1)
    _pg.hotkey('ctrl', 'v')
    time.sleep(0.4)
    if not ensure_foreground(win):
        try:
            _clip.copy(saved)
        except Exception:
            pass
        return False
    _pg.press('enter')
    try:
        _clip.copy(saved)
    except Exception:
        pass
    return True


# --- Scroll-and-stitch capture for replies taller than the window ---


def _content_band(win):
    """(full_bbox, crop_box) where crop_box trims sidebar / title / composer so
    only the scrolling conversation column remains."""
    L, T, R, B = window_rect(win)
    W, H = R - L, B - T
    crop = (int(W * 0.21), int(H * 0.09), W, int(H * 0.86))
    return (L, T, R, B), crop


def _grab_band(win):
    bbox, crop = _content_band(win)
    return ImageGrab.grab(bbox=bbox, all_screens=True).convert('RGB').crop(crop)


def _sig(img):
    return list(img.convert('L').resize((48, 36)).getdata())


def _sig_same(a, b, tol=8, frac=0.02):
    if a is None or b is None:
        return False
    diff = sum(1 for x, y in zip(a, b) if abs(x - y) > tol)
    return diff <= len(a) * frac


def _anchor(win):
    (L, T, R, B), _ = _content_band(win)
    return (L + int((R - L) * 0.62), T + int((B - T) * 0.45))


_WM_MOUSEWHEEL = 0x020A


def _render_hwnd(win):
    """The Chromium render-widget child HWND, which actually scrolls. Falls back
    to the top window."""
    top = _win_handle(win)
    found = []
    try:
        win32gui.EnumChildWindows(
            top,
            lambda c, _: (found.append(c)
                          if 'RenderWidget' in win32gui.GetClassName(c) else None) or True,
            None)
    except Exception:
        pass
    return found[0] if found else top


def wheel(win, notches):
    """Scroll the conversation by posting WM_MOUSEWHEEL to the renderer.
    notches > 0 scrolls up, < 0 scrolls down. Works without foreground and
    without moving the real mouse (pyautogui's wheel is ignored by Chromium)."""
    target = _render_hwnd(win)
    try:
        l, t, r, b = win32gui.GetWindowRect(target)
    except Exception:
        return
    cx, cy = (l + r) // 2, (t + b) // 2
    delta = int(notches * 120)
    wParam = (delta << 16) & 0xFFFFFFFF
    lParam = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
    try:
        win32gui.PostMessage(target, _WM_MOUSEWHEEL, wParam, lParam)
    except Exception:
        pass


def _scroll_step(win, notches, settle=0.33):
    """Scroll one gentle step and report whether the view actually moved.
    Gentle single steps (vs rapid bursts) avoid Chromium smooth-scroll momentum
    that otherwise swallows subsequent steps."""
    before = _sig(_grab_band(win))
    wheel(win, notches)
    time.sleep(settle)
    return not _sig_same(_sig(_grab_band(win)), before)


def _scroll_to_edge(win, up, max_steps=80):
    """Scroll to the top (up=True) or bottom using verified steps; stops after
    two consecutive non-moving steps (the boundary)."""
    d = 4 if up else -4
    stuck = 0
    for _ in range(max_steps):
        if _scroll_step(win, d):
            stuck = 0
        else:
            stuck += 1
            if stuck >= 2:
                return


def scroll_to_bottom(win):
    _scroll_to_edge(win, up=False)


def stitch_vertical(frames, debug=False):
    """Stitch a top-to-bottom list of equal-width frames into one tall image,
    removing the overlap between consecutive frames via grayscale correlation."""
    import numpy as np
    from PIL import Image as _Image
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0]
    SCALE_W = 100
    smalls, ratios = [], []
    for f in frames:
        g = f.convert('L')
        h = max(1, round(g.height * SCALE_W / g.width))
        smalls.append(np.asarray(g.resize((SCALE_W, h)), dtype=np.int16))
        ratios.append(f.height / h)
    out = np.asarray(frames[0].convert('RGB'))
    acc = smalls[0]
    for i in range(1, len(frames)):
        a, b = acc, smalls[i]
        K = max(1, min(30, b.shape[0] // 3))
        bw = b[:K]
        a_h = a.shape[0]
        best_ov, best_score = None, None
        for ov in range(K, min(a_h, b.shape[0]) + 1):
            seg = a[a_h - ov:a_h - ov + K]
            if seg.shape[0] != K:
                break
            score = float(np.abs(seg - bw).mean())
            if best_score is None or score < best_score:
                best_score, best_ov = score, ov
        if best_ov is None:
            best_ov = b.shape[0] // 2
        ov_full = max(0, min(int(round(best_ov * ratios[i])), frames[i].height))
        if debug:
            print('  stitch pair %d: ov_small=%s score=%.1f ov_px=%d band_h=%d'
                  % (i, best_ov, best_score or -1, ov_full, frames[i].height))
        add = np.asarray(frames[i].convert('RGB'))[ov_full:]
        if add.size:
            out = np.vstack([out, add])
        acc = np.vstack([acc, b[best_ov:]])
    return _Image.fromarray(out)


def _force_relayout(win):
    """Resize the window slightly to force Chromium to re-layout, which pins the
    scroll to the bottom and cancels smooth-scroll momentum. Scrolling right
    after a reply is otherwise unreliable. Returns the saved (l,t,w,h) to restore."""
    if not win32gui:
        return None
    try:
        h = _win_handle(win)
        l, t, r, b = win32gui.GetWindowRect(h)
        w0, h0 = r - l, b - t
        # Two resizes (grow then shrink) reliably reset the scroll/anchor state;
        # a single resize sometimes doesn't. Capture runs at the shrunk size.
        win32gui.SetWindowPos(h, 0, l, t, w0, h0 + 60, 0x0004)  # SWP_NOZORDER
        time.sleep(0.5)
        win32gui.SetWindowPos(h, 0, l, t, w0, max(320, h0 - 40), 0x0004)
        time.sleep(0.6)
        return (l, t, w0, h0)
    except Exception:
        return None


def _restore_size(win, saved):
    if not win32gui or not saved:
        return
    try:
        l, t, w0, h0 = saved
        win32gui.SetWindowPos(_win_handle(win), 0, l, t, w0, h0, 0x0004)
        time.sleep(0.3)
    except Exception:
        pass


def capture_full_reply(win, out_png, max_frames=60, step_notches=2, debug=False):
    """Capture the whole conversation as one tall stitched PNG.

    ChatGPT keeps an auto-follow anchor pinned to the bottom for some seconds
    after a reply, which fights scrolling (causing skipped middles / truncation).
    So: (1) resize to reset state, (2) settle at the bottom which is always
    reachable, (3) WAIT until an up-scroll actually moves -- that is the moment
    the anchor releases -- then (4) go to the top and (5) capture downward with
    the anchor's grain. Returns (path, (w, h), n)."""
    saved = _force_relayout(win)       # reset scroll state
    _scroll_to_edge(win, up=False)     # settle at the bottom (anchor-aligned)

    for k in range(15):                # wait for the auto-follow anchor to release
        moves = sum(1 for _ in range(3) if _scroll_step(win, 4))
        if debug:
            print('  scroll-release test %d: %d/3 moved' % (k, moves))
        if moves >= 3:                 # consistently scrollable -> released
            break
        time.sleep(1.3)

    stuck = 0
    for i in range(120):               # go to the very top (verified)
        if _scroll_step(win, 4):
            stuck = 0
        else:
            stuck += 1
            if stuck >= 2:
                break
    time.sleep(0.6)                    # let momentum settle at the top
    frames = []
    while len(frames) < max_frames:
        frames.append(_grab_band(win))
        moved = _scroll_step(win, -step_notches)       # scroll down
        if not moved:
            moved = _scroll_step(win, -step_notches)   # retry once (missed event)
        if debug:
            print('  down frames=%d moved=%s' % (len(frames), moved))
        if not moved:
            break                                      # bottom reached
    if debug:                          # frames are already top -> bottom
        print('  captured %d frames' % len(frames))
    stitched = stitch_vertical(frames, debug=debug)
    stitched.save(out_png)
    _restore_size(win, saved)          # put the window back
    return out_png, stitched.size, len(frames)
