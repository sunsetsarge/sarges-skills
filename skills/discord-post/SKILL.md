---
name: discord-post
argument-hint: "<message> --channel <name> [--react] [--dry-run]"
description: Post a message to a channel in Blaine's Discord server (SaspanSalt) using the C1-10P bot. Use when the user wants Claude to SEND / POST / ANNOUNCE / DROP something into their Discord - e.g. "post this to my Discord", "announce it in #ideas", "send that to my server", "message my Discord", "drop this note in #notes", "put this in the apis channel". Resolves the channel by NAME (you can say "#ideas" or just "ideas"), auto-splits long messages, and can add a checkmark reaction. Do NOT use for: YouTube-link logging (that is automatic via #links-youtube + the discord-youtube-logger), Discord server SETUP like creating channels/roles/settings (that is the discord-setup MCP), or reading/monitoring channels. Windows; needs the bot token at ~/.discord-mcp/config.json.
---

# Discord Post

Sends a message to any channel in Blaine's **SaspanSalt** Discord using the **C1-10P** bot,
over the Discord REST API. The `discord-setup` MCP can only manage channels/roles/settings —
it cannot post — so message-sending goes through this skill's script (same bot token).

> The server is private (just Blaine + the bot). Still: **confirm the target channel and the
> content with Blaine before posting** unless he clearly gave both, and prefer `--dry-run`
> first for anything long or important. Never post secrets/tokens.

## Requirements
- **Python: `C:\AI-Shared\python.exe`** (3.10). stdlib only — no packages needed.
- Bot token at `C:\Users\blain\.discord-mcp\config.json` (key `discordToken`), or the
  `DISCORD_BOT_TOKEN` env var. The bot must be in the target server.

Scripts live in this skill's `scripts/` folder.

## Post a message (primary)
```bash
# by channel name (with or without the leading #)
C:\AI-Shared\python.exe scripts\discord_post.py send --channel ideas --text "Shipped the new mockups 🎉"

# multi-line / long content from a file (auto-split into <=2000-char messages)
C:\AI-Shared\python.exe scripts\discord_post.py send --channel notes --file C:\path\to\note.md

# add a checkmark reaction to the posted message (e.g. to mark it 'done/logged')
C:\AI-Shared\python.exe scripts\discord_post.py send --channel to-do --text "Order filament" --react

# ALWAYS available: preview without posting
C:\AI-Shared\python.exe scripts\discord_post.py send --channel ideas --text "draft..." --dry-run
```

## Discover channels
```bash
C:\AI-Shared\python.exe scripts\discord_post.py channels     # prints:  <id>  #<name>
C:\AI-Shared\python.exe scripts\discord_post.py whoami       # verify the bot + server count
```
If a name is ambiguous or not found, the script says so and points you to `channels`.

## Notes / how it works
- **Channel resolution:** exact name match first, then a unique partial match, else it errors
  (never guesses between two channels). Numeric input is treated as a channel id directly.
- **Unicode is safe:** the body is sent as JSON (`\uXXXX` escapes), so emoji and em-dashes
  render correctly — unlike raw PowerShell REST calls, which mangle UTF-8 unless byte-encoded.
- **Rate limits:** ~0.7s between chunks; HTTP 429 is honored with the server's `retry_after`.
- **Guild:** if the bot is ever in more than one server, pass `--guild <name>`; with one server
  (the current case) it is auto-selected.
- Related tooling: `discord-youtube-logger` (auto-logs YouTube links) and `discord-mcp-ops`
  (the setup-bot's healthcheck/update kit). This skill is the general "post anything" path.
