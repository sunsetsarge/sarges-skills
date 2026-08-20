---
name: windows-control
description: Scripted Windows GUI automation via bundled Python scripts (pyautogui + Windows UI Automation) — click/type/scroll, window focus and management, click-element-by-name, dialog handling, and reading window text without OCR. Use when the computer-use MCP is NOT connected, when a task needs deterministic shell-callable UI steps (scheduled jobs, scripts called by other skills, repeatable multi-step automation), or when the user explicitly asks for pyautogui / UI Automation scripting. Do NOT use for ordinary interactive desktop control when the computer-use MCP is available (prefer the MCP), for browser tasks (use claude-in-chrome), or for driving the ChatGPT desktop app (use the chatgpt-desktop skill).
---

# Windows Control

Deterministic Windows GUI automation through standalone Python scripts in `scripts/`. Every action is a shell command, so sequences are repeatable and can be embedded in other scripts or scheduled tasks.

## Routing — pick this skill only when it wins

| Situation | Use |
|---|---|
| Interactive desktop control, computer-use MCP connected | computer-use MCP, not this skill |
| Anything in a browser | claude-in-chrome MCP |
| Relaying to the ChatGPT app | chatgpt-desktop skill |
| Headless/scheduled/scripted UI steps; MCP unavailable; user asks for pyautogui | **this skill** |

Run scripts with the `py` launcher (falls back: `python`). All paths below are relative to this skill's `scripts/` directory — use the absolute path when calling from another working directory.

## Method ladder — always try the highest rung that applies

1. **UI Automation text** — `read_window.py "<title>"` reads real text from a window. Fast, exact, no OCR.
2. **UI Automation elements** — `read_ui_elements.py "<title>"` lists buttons/links/tabs/inputs with coordinates; `click_element.py "<name>"` clicks by name. No coordinates needed.
3. **Screen-text search** — `find_text.py` / `click_text.py` when the element tree is empty (some Electron/UWP apps).
4. **Raw coordinates** — `click.py X Y` only after a fresh screenshot confirms the layout.
5. **Screenshot + vision** — `screenshot.py > out.b64` as a fallback for purely visual layouts.
6. **OCR region** — `read_region.py X Y W H` last resort; requires Tesseract installed, otherwise it fails.

## Script reference

**Observe**
```bash
py list_windows.py                       # all open windows (find exact titles here first)
py get_active_window.py                  # title of focused window
py read_window.py "Notepad"              # window text via UI Automation
py read_ui_elements.py "Chrome" --json   # elements + coords (--buttons-only / --links-only)
py screenshot.py > out.b64               # full-screen base64 PNG
py find_text.py "Login" "Chrome"         # coordinates of visible text
```

**Act**
```bash
py focus_window.py "Notepad"             # bring to front — ALWAYS before typing
py click_element.py "Save" --window "Notepad" --type Button
py click_text.py "Submit" "Chrome"       # click visible text when no element matches
py click.py 500 300 [right|left] [2]     # coordinate click / right / double
py type_text.py "Hello"                  # types into whatever has focus
py key_press.py "ctrl+s"                 # also: enter, alt+tab, win, ctrl+shift+esc
py mouse_move.py 500 300
py scroll.py down 5
py drag.py 100 100 500 300
py minimize_window.py / maximize_window.py / close_window.py "<title>"
```

**Synchronize** (use these instead of sleeps)
```bash
py wait_for_window.py "Notepad" 10       # wait up to 10s for window
py wait_for_text.py "Ready" "App" 30     # wait up to 30s for text to appear
```

**Dialogs** — never blind-type into Save/Open dialogs; drive them explicitly:
```bash
py handle_dialog.py wait "Save As" --timeout 5
py handle_dialog.py read
py handle_dialog.py type "C:\path\to\file" --field 0
py handle_dialog.py click "Save"
py handle_dialog.py dismiss              # auto-finds OK/Close/Cancel
```

## Standard workflow

1. `list_windows.py` → get the exact window title.
2. `focus_window.py` + `wait_for_window.py` → guarantee the target has focus.
3. Read (`read_window.py` / `read_ui_elements.py`) → know the current state.
4. Act (highest ladder rung available).
5. Synchronize (`wait_for_text.py` / `handle_dialog.py wait`) → don't assume the UI updated.
6. Read again → verify the change actually happened before reporting success.

## Edge cases and traps

- **Focus is global state.** `type_text.py` and `key_press.py` go to whichever window has focus at that instant. Anything (a notification, another script) can steal focus between commands — re-focus before every typing burst, and verify with `get_active_window.py` when a sequence matters.
- **Window-title matching is partial.** "Chrome" matches the first window whose title contains it; with multiple matches (several Chrome windows, a file named "chrome.txt" open in Notepad) you may hit the wrong one. Get exact titles from `list_windows.py` and pass the most specific substring.
- **Elevated (admin) windows silently ignore input** sent from a non-elevated Python process. No error is raised — the click just does nothing. If a UAC prompt or admin app is the target, tell the user; don't retry in a loop.
- **Electron/UWP apps often expose empty or shallow UIA trees.** If `read_ui_elements.py` returns little or `click_element.py` finds nothing, that's expected — drop to `click_text.py`, then coordinates.
- **Don't assume screen geometry.** Resolution and DPI scaling vary; on multi-monitor setups coordinates can be negative (monitor left of / above primary). Take a screenshot first and derive coordinates from it; verify a coordinate click landed by reading state afterward.
- **Launching apps:** prefer starting them directly from the shell (`start notepad`) over Win-key + type, which is timing-sensitive. If you must use the Start menu, `wait_for_window.py` before typing anything.
- **Abort switch:** pyautogui FAILSAFE is on — slamming the mouse to the top-left corner (0,0) raises an exception and stops the script. Don't park the mouse there intentionally.
- **Pacing:** scripts insert small delays, but slow apps need `wait_for_*`, not hope. Never chain click → type without a wait or a read in between.

## Example — open Notepad and save a file (correct pattern)

```bash
cmd //c start notepad
py wait_for_window.py "Notepad" 10
py focus_window.py "Notepad"
py type_text.py "Hello from automation"
py key_press.py "ctrl+s"
py handle_dialog.py wait "Save As" --timeout 5
py handle_dialog.py type "C:\Users\<user>\Desktop\note.txt" --field 0
py handle_dialog.py click "Save"
py read_window.py "note.txt - Notepad"   # verify: title changed = save succeeded
```

## Requirements

- Python 3.11+ with `pyautogui` and `pillow` (installed)
- `read_region.py` only: Tesseract OCR (not installed by default — prefer `read_window.py`)
