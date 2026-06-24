---
name: chatgpt-desktop
argument-hint: "<question | image prompt> [--new] [--full] [--out PATH] [--raw]"
description: Ask the ChatGPT desktop app a question and read the reply, OR generate an image with ChatGPT/DALL-E and save it as a full-resolution PNG, by driving the Windows app (focus, type, screenshot, copy-image). Use ONLY when the user explicitly names ChatGPT — e.g. "ask ChatGPT", "what does ChatGPT say", "get a second opinion from ChatGPT", "relay this to ChatGPT", or "make an image with ChatGPT/DALL-E". Do NOT trigger for generic image generation (route plain "make an image / picture" requests to ComfyUI, Stability, or Adobe) or for general questions Claude can answer directly. Windows-only; the ChatGPT desktop app must be installed and logged in.
---

# ChatGPT Desktop (Windows) Skill

Lets Claude send a prompt to the **ChatGPT Windows desktop app** and read its reply.
The app is Chromium-based and exposes no text via UI Automation, so it's driven like a
human: focus the window, paste the prompt, press Enter, wait for the reply to finish,
and screenshot it. Claude reads the screenshot.

> Built as the Windows-native replacement for the macOS-only `claude-chatgpt-mcp` MCP,
> which can't run on Windows (it uses AppleScript).

## Gotchas

- **Do not trigger for generic image generation.** This skill is only for when the user explicitly wants **ChatGPT / DALL-E** (or a ChatGPT "second opinion"). Plain "make an image / picture" requests should route to ComfyUI, Stability, or Adobe — not here. Fire only on an explicit ChatGPT mention.

## Requirements

- **Python: `C:\AI-Shared\python.exe`** (3.10). The `py` launcher is broken in this
  environment — always use the full path. Packages `pyautogui`, `pywinauto`, `pywin32`,
  `Pillow`, `numpy` are installed there.
- ChatGPT desktop app installed and **logged in**
  (`OpenAI.ChatGPT-Desktop`, launch AUMID `OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0!ChatGPT`).

Scripts live in this skill's `scripts/` folder. Run them with the full Python path.

## Ask a question (primary)

```bash
# New chat (recommended); screenshot of the reply is saved next to the script as answer.png
C:\AI-Shared\python.exe scripts\ask_chatgpt.py "your question" --new

# Continue the current chat instead of a new one
C:\AI-Shared\python.exe scripts\ask_chatgpt.py "follow-up question"
```

Then **Read the saved `answer.png`** to get ChatGPT's reply. Options:
`--out <png>`  `--timeout <sec>`  `--no-send` (type but don't submit; for debugging)
`--click` (force-click the composer if auto-focus fails).

## Generate an image

Send an image prompt, wait for generation, then pull the **full-resolution** image
off the clipboard (right-click → "Copy image" via keyboard) and save it as PNG:

```bash
C:\AI-Shared\python.exe scripts\gen_image.py "a red apple on a white background" --out apple.png
C:\AI-Shared\python.exe scripts\gen_image.py "logo for a coffee shop, flat vector" --out logo.png
```

- A "Generate an image:" prefix is added automatically unless the prompt already reads
  like an image request (use `--raw` to send it verbatim).
- Output is the actual generated image (e.g. 1024–1536 px), **not** a screenshot.
- `--retries N` auto-retries when ChatGPT returns "Image generation failed" (a common
  transient error). Other options: `--timeout <sec>`, `--no-new`, `--ix/--iy` (right-click
  target fractions, if the image isn't where expected — see `gen_state.png`).
- After saving, **Read the PNG** to show/use the image.

## Capture a long reply in full (scroll-and-stitch)

For replies taller than the window, stitch the whole thing into one tall PNG:

```bash
C:\AI-Shared\python.exe scripts\ask_chatgpt.py "long question" --new --full --out reply.png
```

Or capture whatever reply is **currently** on screen (best on a chat that has been idle
a few seconds — see limitations):

```bash
C:\AI-Shared\python.exe scripts\capture_full.py reply.png
```

## Other

```bash
C:\AI-Shared\python.exe scripts\shot.py            # screenshot the current ChatGPT window
```

## How it works (so you can debug)

1. Find the ChatGPT window by its **process** (`ChatGPT.exe`), not its title (the app
   renames the window to the conversation title).
2. Force it to the **foreground** (`SetForegroundWindow` + ALT-unlock). If it can't be
   made a stable foreground window it **aborts** rather than type into the wrong app.
3. `Ctrl+N` for a new chat, **paste** the prompt via the clipboard, press **Enter**.
4. Poll a fingerprint of the inner conversation area until it stops changing (reply done).
5. Screenshot the window. For `--full`: wait for ChatGPT's auto-follow anchor to release,
   scroll to the top, then capture downward frame-by-frame and stitch with overlap
   detection (numpy).

## Limitations / tips

- **Reading is visual** — the reply is read from a screenshot (Chromium hides its text
  tree). Claude reads it accurately; plain scripts would need OCR.
- **Focus on a busy desktop.** Automation uses global keyboard/mouse. If another app
  steals focus at the wrong moment the run aborts (safe) — just retry, ideally with the
  ChatGPT window already visible and not buried.
- **`--full` is best-effort.** The stitch engine is solid, but ChatGPT pins new replies
  to the bottom for several seconds (auto-follow), which fights scrolling. `--full` waits
  for that to release; if a capture looks truncated, wait a few seconds and re-run
  `capture_full.py` on the settled chat (most reliable).
- **Reasoning effort** is set in the composer's dropdown (e.g. "High") and adds latency.
- The window may be **maximized/minimized/resized** during automation (focus + capture).
- Multi-monitor and HiDPI are handled (scripts are DPI-aware, use absolute coordinates).
